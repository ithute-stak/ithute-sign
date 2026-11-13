using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;

namespace IthuteSign.Modern;

/// <summary>
/// Records explicit consent for the exact PDF already displayed to the borrower.
/// This is evidence collection only, never contract execution or signing approval.
/// </summary>
public sealed class LoanHubDocumentConsentClient
{
    private readonly HttpClient _http;

    public LoanHubDocumentConsentClient(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        if (_http.BaseAddress?.Scheme != Uri.UriSchemeHttps ||
            !string.IsNullOrEmpty(_http.BaseAddress.UserInfo) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Query) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Fragment))
            throw new ArgumentException("Approved HTTPS LoanHub origin required.", nameof(http));
    }

    public async Task<PreparedLoanHubIntent> RecordConsentAsync(
        PreparedLoanHubIntent prepared, Guid companyId, string signerConfirmation,
        string consentReference, string displayedPdfSha256, string accessToken,
        string bridgeSession, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(prepared);
        if (prepared.IntentId == Guid.Empty || prepared.CompanyId != companyId ||
            !string.Equals(prepared.Status, "prepared", StringComparison.OrdinalIgnoreCase) ||
            prepared.ExpiresAt <= DateTimeOffset.UtcNow ||
            prepared.SigningAuthorized || prepared.SignedContractCreated ||
            prepared.SignatureReuseAllowed)
            throw new InvalidOperationException("A current, exact-document prepared intent is required.");
        if (string.IsNullOrWhiteSpace(signerConfirmation) ||
            signerConfirmation.Length > 100 ||
            string.IsNullOrWhiteSpace(consentReference) ||
            consentReference.Length is < 4 or > 180)
            throw new ArgumentException("Explicit signer confirmation and a consent reference are required.");
        if (!string.Equals(displayedPdfSha256, prepared.DocumentSha256, StringComparison.Ordinal) ||
            displayedPdfSha256 is not { Length: 64 } ||
            !displayedPdfSha256.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f'))
            throw new InvalidOperationException("The displayed PDF does not match the prepared contract.");
        if (string.IsNullOrWhiteSpace(accessToken) || string.IsNullOrWhiteSpace(bridgeSession))
            throw new UnauthorizedAccessException("Authenticated operator and verified workstation required.");

        using var request = new HttpRequestMessage(HttpMethod.Post,
            $"api/v1/wacom-document-intents/{prepared.IntentId:D}/consent")
        {
            Content = JsonContent.Create(new
            {
                signer_confirmation = signerConfirmation,
                consent_reference = consentReference,
                displayed_document_sha256 = displayedPdfSha256
            })
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        request.Headers.Add("X-Company-ID", companyId.ToString("D"));
        request.Headers.Add("X-Wacom-Bridge-Session", bridgeSession);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoStore = true };
        using var response = await _http.SendAsync(request, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("LoanHub rejected document consent authorization.");
        response.EnsureSuccessStatusCode();
        var consented = await response.Content.ReadFromJsonAsync<PreparedLoanHubIntent>(
            cancellationToken: cancellationToken);
        if (consented is null || consented.IntentId != prepared.IntentId ||
            consented.CompanyId != companyId || consented.BorrowerId != prepared.BorrowerId ||
            consented.ContractId != prepared.ContractId ||
            consented.DocumentSha256 != displayedPdfSha256 ||
            consented.DocumentVersion != prepared.DocumentVersion ||
            !string.Equals(consented.Status, "consented", StringComparison.OrdinalIgnoreCase) ||
            consented.SigningAuthorized || consented.SignedContractCreated ||
            consented.SignatureReuseAllowed)
            throw new InvalidOperationException("LoanHub returned an invalid consent state.");
        return consented;
    }
}
