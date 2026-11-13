using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace IthuteSign.Modern;

/// <summary>
/// Read-only adapter for LoanHub's existing Wacom endpoints. The caller must supply
/// an authenticated employee bearer token and a live, enrolled bridge session.
/// Never persist either token, and never use this client to finalize a signature.
/// </summary>
internal sealed class UnsignedContractLookupClient
{
    private readonly HttpClient _http;

    internal UnsignedContractLookupClient(HttpClient http) => _http = http;

    internal async Task<UnsignedClientDocuments> FindAsync(
        string nationalId, Guid companyId, string bearerToken,
        string bridgeSessionToken, CancellationToken cancellationToken = default)
    {
        if (_http.BaseAddress?.Scheme != Uri.UriSchemeHttps ||
            !string.IsNullOrEmpty(_http.BaseAddress.UserInfo))
            throw new InvalidOperationException("A verified HTTPS LoanHub endpoint is required.");
        if (companyId == Guid.Empty || string.IsNullOrWhiteSpace(bearerToken) ||
            string.IsNullOrWhiteSpace(bridgeSessionToken))
            throw new UnauthorizedAccessException("Staff, company and enrolled bridge session are required.");
        if (nationalId != nationalId.Trim() || nationalId.Length is < 4 or > 50 ||
            nationalId.Any(char.IsControl) || nationalId.Any(char.IsWhiteSpace))
            throw new ArgumentException("Invalid National ID.", nameof(nationalId));

        using var lookup = Request(HttpMethod.Post, "api/v1/local-signatures/clients/lookup",
            companyId, bearerToken, bridgeSessionToken);
        lookup.Content = JsonContent.Create(new { national_id = nationalId });
        using var lookupResponse = await _http.SendAsync(lookup, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        await RequireSuccessAsync(lookupResponse, cancellationToken);
        using var identity = await JsonDocument.ParseAsync(
            await lookupResponse.Content.ReadAsStreamAsync(cancellationToken), cancellationToken: cancellationToken);
        var root = identity.RootElement;
        var status = root.GetProperty("status").GetString();
        if (status == "not_found")
            return new UnsignedClientDocuments(null, null, Array.Empty<UnsignedLoanContract>());
        if (status != "matched" || !root.TryGetProperty("client", out var client) ||
            !Guid.TryParse(client.GetProperty("borrower_id").GetString(), out var borrowerId) ||
            borrowerId == Guid.Empty)
            throw new InvalidOperationException("LoanHub client lookup was ambiguous or invalid.");
        var name = client.GetProperty("full_name").GetString();

        using var request = Request(HttpMethod.Get,
            $"api/v1/wacom-document-intents/borrowers/{borrowerId:D}/eligible-contracts",
            companyId, bearerToken, bridgeSessionToken);
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        await RequireSuccessAsync(response, cancellationToken);
        var payload = await response.Content.ReadFromJsonAsync<EligibleContractsResponse>(
            cancellationToken: cancellationToken);
        if (payload is null || payload.BorrowerId != borrowerId ||
            payload.SigningAuthorized || payload.ContractSigned || payload.Contracts is null ||
            payload.Contracts.Count > 50)
            throw new InvalidOperationException("Invalid or unexpected LoanHub contract response.");
        foreach (var contract in payload.Contracts)
        {
            if (contract.BorrowerId != borrowerId || contract.ContractId == Guid.Empty ||
                contract.SourceFileId == Guid.Empty || string.IsNullOrWhiteSpace(contract.DocumentVersion))
                throw new InvalidOperationException("LoanHub returned an invalid contract binding.");
        }
        return new UnsignedClientDocuments(borrowerId, name, payload.Contracts);
    }

    private static HttpRequestMessage Request(HttpMethod method, string path,
        Guid companyId, string bearer, string bridge)
    {
        var request = new HttpRequestMessage(method, path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearer);
        request.Headers.Add("X-Company-ID", companyId.ToString("D"));
        request.Headers.Add("X-Wacom-Bridge-Session", bridge);
        return request;
    }

    private static async Task RequireSuccessAsync(HttpResponseMessage response, CancellationToken ct)
    {
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("LoanHub denied this employee or bridge session.");
        if (!response.IsSuccessStatusCode)
            throw new HttpRequestException($"LoanHub lookup failed ({(int)response.StatusCode}).");
        if (response.Content.Headers.ContentLength is > 128000)
            throw new InvalidOperationException("LoanHub lookup response exceeded allowed size.");
        await Task.CompletedTask;
    }

    private sealed class EligibleContractsResponse
    {
        [JsonPropertyName("borrower_id")] public Guid BorrowerId { get; set; }
        [JsonPropertyName("contracts")] public List<UnsignedLoanContract>? Contracts { get; set; }
        [JsonPropertyName("signing_authorized")] public bool SigningAuthorized { get; set; }
        [JsonPropertyName("contract_signed")] public bool ContractSigned { get; set; }
    }
}

internal sealed record UnsignedClientDocuments(
    Guid? BorrowerId, string? FullName, IReadOnlyList<UnsignedLoanContract> Contracts);

internal sealed class UnsignedLoanContract
{
    [JsonPropertyName("contract_id")] public Guid ContractId { get; set; }
    [JsonPropertyName("contract_number")] public string? ContractNumber { get; set; }
    [JsonPropertyName("source_file_id")] public Guid SourceFileId { get; set; }
    [JsonPropertyName("document_version")] public string? DocumentVersion { get; set; }
    [JsonPropertyName("borrower_id")] public Guid BorrowerId { get; set; }
}
