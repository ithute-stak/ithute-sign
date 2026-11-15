using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace IthuteSign.Modern;

/// <summary>Read-only server-authoritative contract workflow status. Evidence is not execution.</summary>
public sealed class LoanHubContractWorkflowStatusClient
{
    private readonly HttpClient _http;

    public LoanHubContractWorkflowStatusClient(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        if (_http.BaseAddress?.Scheme != Uri.UriSchemeHttps ||
            !string.IsNullOrEmpty(_http.BaseAddress.UserInfo) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Query) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Fragment))
            throw new ArgumentException("Approved HTTPS LoanHub origin required.", nameof(http));
    }

    public async Task<LoanHubContractWorkflowStatus> GetAsync(
        Guid contractId, Guid companyId, string accessToken,
        CancellationToken cancellationToken = default)
    {
        if (contractId == Guid.Empty || companyId == Guid.Empty)
            throw new ArgumentException("Exact contract and company identity required.");
        if (string.IsNullOrWhiteSpace(accessToken))
            throw new UnauthorizedAccessException("Authenticated operator required.");

        using var request = new HttpRequestMessage(HttpMethod.Get,
            $"api/v1/wacom-pdf-candidate-verification/contracts/{contractId:D}/workflow-status");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        request.Headers.Add("X-Company-ID", companyId.ToString("D"));
        request.Headers.CacheControl = new CacheControlHeaderValue { NoStore = true, NoCache = true };
        using var response = await _http.SendAsync(request, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("LoanHub rejected contract status access.");
        response.EnsureSuccessStatusCode();
        var status = await response.Content.ReadFromJsonAsync<LoanHubContractWorkflowStatus>(
            cancellationToken: cancellationToken);
        if (status is null || status.ContractId != contractId ||
            (status.CandidateArchived && !IsSha256(status.CandidateSha256)) ||
            (status.ContractSigned && !status.LegalExecutionVerified))
            throw new InvalidOperationException("LoanHub returned an inconsistent signing status.");
        return status;
    }

    private static bool IsSha256(string? value) =>
        value is { Length: 64 } &&
        value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
}

public sealed class LoanHubContractWorkflowStatus
{
    [JsonPropertyName("contract_id")] public Guid ContractId { get; set; }
    [JsonPropertyName("candidate_archived")] public bool CandidateArchived { get; set; }
    [JsonPropertyName("candidate_sha256")] public string? CandidateSha256 { get; set; }
    [JsonPropertyName("ceremony_status")] public string? CeremonyStatus { get; set; }
    [JsonPropertyName("borrower_affirmed")] public bool BorrowerAffirmed { get; set; }
    [JsonPropertyName("workstation_key_verified")] public bool WorkstationKeyVerified { get; set; }
    [JsonPropertyName("physical_stu540_verified")] public bool PhysicalStu540Verified { get; set; }
    [JsonPropertyName("legal_execution_verified")] public bool LegalExecutionVerified { get; set; }
    [JsonPropertyName("contract_signed")] public bool ContractSigned { get; set; }
}
