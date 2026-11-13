using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace IthuteSign.Modern;

/// <summary>
/// Prepares an exact-document consent/evidence intent; does not sign a contract.
/// The existing LoanHub server is authoritative for PDF identity and permissions.
/// </summary>
public sealed class LoanHubDocumentIntentClient
{
    private readonly HttpClient _http;

    public LoanHubDocumentIntentClient(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        if (_http.BaseAddress?.Scheme != Uri.UriSchemeHttps ||
            !string.IsNullOrEmpty(_http.BaseAddress.UserInfo) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Query) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Fragment))
            throw new ArgumentException("Approved HTTPS LoanHub origin required.", nameof(http));
    }

    public async Task<PreparedLoanHubIntent> PrepareAsync(
        EligibleLoanHubContract contract, Guid companyId, Guid workstationId,
        string accessToken, string bridgeSession, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(contract);
        if (contract.BorrowerId == Guid.Empty || contract.ContractId == Guid.Empty ||
            contract.SourceFileId == Guid.Empty || companyId == Guid.Empty ||
            workstationId == Guid.Empty || string.IsNullOrWhiteSpace(contract.DocumentVersion))
            throw new ArgumentException("Complete exact-contract and workstation identity required.");
        if (string.IsNullOrWhiteSpace(accessToken) || string.IsNullOrWhiteSpace(bridgeSession))
            throw new UnauthorizedAccessException("Authenticated operator and proven workstation required.");

        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/wacom-document-intents")
        {
            Content = JsonContent.Create(new
            {
                borrower_id = contract.BorrowerId,
                contract_id = contract.ContractId,
                source_file_id = contract.SourceFileId,
                workstation_id = workstationId,
                document_version = contract.DocumentVersion
            })
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        request.Headers.Add("X-Company-ID", companyId.ToString("D"));
        request.Headers.Add("X-Wacom-Bridge-Session", bridgeSession);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoCache = true, NoStore = true };
        using var response = await _http.SendAsync(request, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("LoanHub rejected document intent authorization.");
        response.EnsureSuccessStatusCode();
        if (response.StatusCode != HttpStatusCode.Created)
            throw new InvalidOperationException("Unexpected document-intent response status.");
        var intent = await response.Content.ReadFromJsonAsync<PreparedLoanHubIntent>(
            cancellationToken: cancellationToken);
        if (intent is null || intent.IntentId == Guid.Empty || intent.CompanyId != companyId ||
            intent.BorrowerId != contract.BorrowerId || intent.ContractId != contract.ContractId ||
            !string.Equals(intent.DocumentVersion, contract.DocumentVersion, StringComparison.Ordinal) ||
            !string.Equals(intent.Status, "prepared", StringComparison.OrdinalIgnoreCase) ||
            intent.ExpiresAt <= DateTimeOffset.UtcNow ||
            intent.ExpiresAt > DateTimeOffset.UtcNow.AddMinutes(11) ||
            intent.SigningAuthorized || intent.SignedContractCreated || intent.SignatureReuseAllowed ||
            intent.DocumentSha256 is null || intent.DocumentSha256.Length != 64 ||
            intent.DocumentSha256.Any(c => !Uri.IsHexDigit(c) || char.IsUpper(c)))
            throw new InvalidOperationException("LoanHub returned an invalid exact-document intent.");
        return intent;
    }
}

public sealed class PreparedLoanHubIntent
{
    [JsonPropertyName("intent_id")] public Guid IntentId { get; set; }
    [JsonPropertyName("status")] public string? Status { get; set; }
    [JsonPropertyName("company_id")] public Guid CompanyId { get; set; }
    [JsonPropertyName("borrower_id")] public Guid BorrowerId { get; set; }
    [JsonPropertyName("contract_id")] public Guid ContractId { get; set; }
    [JsonPropertyName("document_sha256")] public string? DocumentSha256 { get; set; }
    [JsonPropertyName("document_version")] public string? DocumentVersion { get; set; }
    [JsonPropertyName("expires_at")] public DateTimeOffset ExpiresAt { get; set; }
    [JsonPropertyName("signing_authorized")] public bool SigningAuthorized { get; set; }
    [JsonPropertyName("signed_contract_created")] public bool SignedContractCreated { get; set; }
    [JsonPropertyName("signature_reuse_allowed")] public bool SignatureReuseAllowed { get; set; }
}
