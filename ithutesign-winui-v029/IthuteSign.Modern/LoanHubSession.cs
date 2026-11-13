using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace IthuteSign.Modern;

/// <summary>
/// Narrow LoanHub authentication client. Never stores credentials or tokens on disk.
/// Login alone does not grant document-signing permission.
/// </summary>
public sealed class LoanHubSession : IDisposable
{
    private readonly HttpClient _http;
    private string? _token;
    public LoanHubUser? User { get; private set; }
    public bool IsAuthenticated => _token is not null && User is not null;

    public LoanHubSession(Uri baseUri, HttpMessageHandler? handler = null)
    {
        if (baseUri.Scheme != Uri.UriSchemeHttps || !string.IsNullOrEmpty(baseUri.UserInfo)
            || !string.IsNullOrEmpty(baseUri.Query) || !string.IsNullOrEmpty(baseUri.Fragment))
            throw new ArgumentException("LoanHub requires a clean HTTPS base URL.", nameof(baseUri));
        _http = handler is null ? new HttpClient() : new HttpClient(handler);
        _http.BaseAddress = new Uri(baseUri.AbsoluteUri.TrimEnd('/') + "/");
        _http.Timeout = TimeSpan.FromSeconds(20);
    }

    public async Task<LoanHubUser> LoginAsync(
        string phone, string password, string? otp = null, CancellationToken cancellationToken = default)
    {
        Logout();
        if (string.IsNullOrWhiteSpace(phone) || string.IsNullOrWhiteSpace(password))
            throw new ArgumentException("Phone and password are required.");

        // LoanHub's existing auth endpoint, not a new IthuteSign identity provider.
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/auth/login")
        {
            Content = JsonContent.Create(new
            {
                phone = phone.Trim(),
                password,
                otp = string.IsNullOrWhiteSpace(otp) ? null : otp.Trim(),
                device_name = "IthuteSign Modern"
            })
        };
        using var response = await _http.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
            throw new LoanHubLoginException(response.StatusCode);
        var payload = await response.Content.ReadFromJsonAsync<LoginPayload>(cancellationToken: cancellationToken);
        if (payload?.User is null || string.IsNullOrWhiteSpace(payload.AccessToken)
            || !string.Equals(payload.TokenType, "bearer", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("LoanHub returned an invalid login response.");
        if (!payload.User.IsActive || payload.User.MustChangePassword)
            throw new UnauthorizedAccessException("Account is inactive or requires a password change in LoanHub.");
        if (payload.User.Memberships is null || !payload.User.Memberships.Any(m => m.IsActive))
            throw new UnauthorizedAccessException("A current company staff membership is required.");
        _token = payload.AccessToken;
        User = payload.User;
        return User;
    }

    public async Task<JsonDocument> GetOperatorAssignmentAsync(
        Guid workstationId, CancellationToken cancellationToken = default)
    {
        if (!IsAuthenticated) throw new UnauthorizedAccessException("Login is required.");
        using var request = new HttpRequestMessage(HttpMethod.Get,
            $"api/v1/contract-signing/workstations/{workstationId:D}/my-assignment");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
        using var response = await _http.SendAsync(request, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
        {
            Logout();
            throw new UnauthorizedAccessException("LoanHub rejected this workstation session.");
        }
        response.EnsureSuccessStatusCode();
        return await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(cancellationToken),
            cancellationToken: cancellationToken);
    }

    /// <summary>
    /// Requests a short-lived nonce for the registered device. This does not
    /// sign the challenge: the enrolled private key must remain in the local
    /// workstation bridge, not in the UI or its preferences.
    /// </summary>
    public async Task<DeviceChallenge> RequestDeviceChallengeAsync(
        Guid workstationId, CancellationToken cancellationToken = default)
    {
        if (!IsAuthenticated) throw new UnauthorizedAccessException("Login is required.");
        using var request = new HttpRequestMessage(HttpMethod.Post, "api/v1/wacom-bridge/device-challenges")
        {
            Content = JsonContent.Create(new { workstation_id = workstationId })
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _token);
        using var response = await _http.SendAsync(request, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
        {
            Logout();
            throw new UnauthorizedAccessException("LoanHub rejected the device challenge request.");
        }
        response.EnsureSuccessStatusCode();
        var challenge = await response.Content.ReadFromJsonAsync<DeviceChallenge>(
            cancellationToken: cancellationToken);
        if (challenge is null || challenge.ChallengeId == Guid.Empty
            || challenge.WorkstationId != workstationId
            || challenge.CompanyId == Guid.Empty || challenge.EmployeeUserId != User?.Id
            || string.IsNullOrWhiteSpace(challenge.Nonce)
            || challenge.ExpiresAt <= DateTimeOffset.UtcNow
            || !challenge.DeviceProofRequired || challenge.SigningAuthorized)
            throw new InvalidOperationException("LoanHub returned an invalid device challenge.");
        return challenge;
    }

    public void Logout() { _token = null; User = null; }
    public void Dispose() { Logout(); _http.Dispose(); }

    private sealed class LoginPayload
    {
        [JsonPropertyName("access_token")] public string? AccessToken { get; set; }
        [JsonPropertyName("token_type")] public string? TokenType { get; set; }
        [JsonPropertyName("user")] public LoanHubUser? User { get; set; }
    }
}

public sealed class LoanHubUser
{
    [JsonPropertyName("id")] public Guid Id { get; set; }
    [JsonPropertyName("phone")] public string? Phone { get; set; }
    [JsonPropertyName("role")] public string? Role { get; set; }
    [JsonPropertyName("is_active")] public bool IsActive { get; set; }
    [JsonPropertyName("must_change_password")] public bool MustChangePassword { get; set; }
    [JsonPropertyName("memberships")] public List<LoanHubMembership>? Memberships { get; set; }
}
public sealed class LoanHubMembership
{
    [JsonPropertyName("company_id")] public Guid CompanyId { get; set; }
    [JsonPropertyName("is_active")] public bool IsActive { get; set; }
    [JsonPropertyName("role")] public string? Role { get; set; }
}
public sealed class LoanHubLoginException : Exception
{
    public HttpStatusCode StatusCode { get; }
    public LoanHubLoginException(HttpStatusCode code) : base("LoanHub login failed. Verify credentials and any required second factor.")
        => StatusCode = code;
}

public sealed class DeviceChallenge
{
    [JsonPropertyName("challenge_id")] public Guid ChallengeId { get; set; }
    [JsonPropertyName("workstation_id")] public Guid WorkstationId { get; set; }
    [JsonPropertyName("company_id")] public Guid CompanyId { get; set; }
    [JsonPropertyName("employee_user_id")] public Guid EmployeeUserId { get; set; }
    [JsonPropertyName("nonce")] public string? Nonce { get; set; }
    [JsonPropertyName("expires_at")] public DateTimeOffset ExpiresAt { get; set; }
    [JsonPropertyName("device_proof_required")] public bool DeviceProofRequired { get; set; }
    [JsonPropertyName("signing_authorized")] public bool SigningAuthorized { get; set; }
}
