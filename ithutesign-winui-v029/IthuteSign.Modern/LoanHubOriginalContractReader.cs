using System.Net;
using System.Net.Http.Headers;
using System.Security.Cryptography;

namespace IthuteSign.Modern;

/// <summary>
/// Retrieves the exact original LoanHub contract into memory for review only.
/// No local file write, signature placement, or contract-state mutation.
/// </summary>
public sealed class LoanHubOriginalContractReader
{
    private const int MaxPdfBytes = 20 * 1024 * 1024;
    private readonly HttpClient _http;

    public LoanHubOriginalContractReader(HttpClient http)
    {
        _http = http ?? throw new ArgumentNullException(nameof(http));
        if (_http.BaseAddress?.Scheme != Uri.UriSchemeHttps ||
            !string.IsNullOrEmpty(_http.BaseAddress.UserInfo) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Query) ||
            !string.IsNullOrEmpty(_http.BaseAddress.Fragment))
            throw new ArgumentException("Approved HTTPS LoanHub origin required.", nameof(http));
    }

    public async Task<byte[]> ReadOriginalPdfAsync(
        PreparedLoanHubIntent intent, Guid companyId, string accessToken,
        string bridgeSession, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(intent);
        if (intent.IntentId == Guid.Empty || intent.CompanyId != companyId ||
            intent.ExpiresAt <= DateTimeOffset.UtcNow ||
            intent.SigningAuthorized || intent.SignedContractCreated ||
            string.IsNullOrWhiteSpace(accessToken) || string.IsNullOrWhiteSpace(bridgeSession) ||
            !IsSha256(intent.DocumentSha256))
            throw new UnauthorizedAccessException("Valid prepared document and verified workstation required.");

        using var request = new HttpRequestMessage(HttpMethod.Get,
            $"api/v1/wacom-document-intents/{intent.IntentId:D}/source-pdf");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);
        request.Headers.Add("X-Company-ID", companyId.ToString("D"));
        request.Headers.Add("X-Wacom-Bridge-Session", bridgeSession);
        request.Headers.CacheControl = new CacheControlHeaderValue { NoStore = true };
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("LoanHub rejected original-document access.");
        response.EnsureSuccessStatusCode();
        if (response.Content.Headers.ContentType?.MediaType != "application/pdf" ||
            response.Content.Headers.ContentLength is > MaxPdfBytes or <= 0 ||
            response.Headers.TryGetValues("X-Wacom-Signing-Authorized", out var signingValues) &&
                signingValues.Any(v => !string.Equals(v, "false", StringComparison.OrdinalIgnoreCase)))
            throw new InvalidOperationException("LoanHub returned an unexpected document response.");
        if (!response.Headers.TryGetValues("X-Wacom-Original-SHA256", out var hashes) ||
            hashes.Count() != 1 || !string.Equals(hashes.Single(), intent.DocumentSha256, StringComparison.Ordinal))
            throw new InvalidOperationException("Original contract identity mismatch.");

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var buffer = new MemoryStream();
        var chunk = new byte[8192];
        int read;
        while ((read = await stream.ReadAsync(chunk.AsMemory(), cancellationToken)) != 0)
        {
            if (buffer.Length + read > MaxPdfBytes)
                throw new InvalidOperationException("Contract exceeds verified PDF size limit.");
            buffer.Write(chunk, 0, read);
        }
        var bytes = buffer.ToArray();
        if (bytes.Length < 5 || bytes[0] != (byte)'%' || bytes[1] != (byte)'P' ||
            bytes[2] != (byte)'D' || bytes[3] != (byte)'F' || bytes[4] != (byte)'-')
            throw new InvalidOperationException("Original contract is not a PDF.");
        var actualHash = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        if (!string.Equals(actualHash, intent.DocumentSha256, StringComparison.Ordinal))
            throw new InvalidOperationException("Original contract checksum mismatch.");
        return bytes;
    }

    private static bool IsSha256(string? value) =>
        value is { Length: 64 } && value.All(c => c is >= '0' and <= '9' or >= 'a' and <= 'f');
}
