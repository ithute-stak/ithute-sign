using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace IthuteSign.Modern;

/// <summary>
/// Read-only contract discovery. Requires a proven, in-memory connector session.
/// Never turns an eligible contract into a signing authorization.
/// </summary>
public sealed class LoanHubContractDiscovery
{
    private readonly HttpClient _http;

    public LoanHubContractDiscovery(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        if (_http.BaseAddress?.Scheme != Uri.UriSchemeHttps ||
            !string.IsNullOrEmpty(_http.BaseAddress.UserInfo) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Query) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Fragment))
            throw new ArgumentException("An approved HTTPS LoanHub origin is required.", nameof(http));
    }

    public async Task<IReadOnlyList<EligibleLoanHubContract>> GetEligibleContractsAsync(
        Guid borrowerId, Guid companyId, string accessToken, string bridgeSession,
        CancellationToken cancellationToken = default)
    {
        if (borrowerId == Guid.Empty || companyId == Guid.Empty)
            throw new ArgumentException("Borrower and company IDs are required.");
        if (string.IsNullOrWhiteSpace(accessToken) || string.IsNullOrWhiteSpace(bridgeSession))
            throw new UnauthorizedAccessException("Employee authentication and verified workstation session are required.");
        // A connector session must never be stored on disk, logged, or embedded in a URL.
        using var request = new HttpRequestMessage(HttpMethod.Get,
            $"api/v1/wacom-document-intents/borrowers/{borrowerId:D}/eligible-contracts");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        request.Headers.Add("X-Company-ID", companyId.ToString("D"));
        request.Headers.Add("X-Wacom-Bridge-Session", bridgeSession);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("LoanHub rejected employee or workstation authorization.");
        response.EnsureSuccessStatusCode();
        var payload = await response.Content.ReadFromJsonAsync<EligibleContractsResponse>(
            cancellationToken: cancellationToken);
        if (payload is null || payload.BorrowerId != borrowerId ||
            payload.SigningAuthorized || payload.ContractSigned || payload.Contracts is null ||
            payload.Contracts.Count > 50)
            throw new InvalidOperationException("Invalid LoanHub contract-discovery response.");
        var seen = new HashSet<Guid>();
        foreach (var contract in payload.Contracts)
        {
            if (contract.BorrowerId != borrowerId || contract.ContractId == Guid.Empty ||
                contract.SourceFileId == Guid.Empty || string.IsNullOrWhiteSpace(contract.DocumentVersion) ||
                string.IsNullOrWhiteSpace(contract.ContractNumber) || !seen.Add(contract.ContractId))
                throw new InvalidOperationException("Untrusted contract identity in discovery response.");
        }
        return payload.Contracts.AsReadOnly();
    }

    private sealed class EligibleContractsResponse
    {
        [JsonPropertyName("borrower_id")] public Guid BorrowerId { get; set; }
        [JsonPropertyName("contracts")] public List<EligibleLoanHubContract>? Contracts { get; set; }
        [JsonPropertyName("signing_authorized")] public bool SigningAuthorized { get; set; }
        [JsonPropertyName("contract_signed")] public bool ContractSigned { get; set; }
    }
}

public sealed class EligibleLoanHubContract
{
    [JsonPropertyName("borrower_id")] public Guid BorrowerId { get; set; }
    [JsonPropertyName("contract_id")] public Guid ContractId { get; set; }
    [JsonPropertyName("contract_number")] public string? ContractNumber { get; set; }
    [JsonPropertyName("source_file_id")] public Guid SourceFileId { get; set; }
    [JsonPropertyName("document_version")] public string? DocumentVersion { get; set; }
}
