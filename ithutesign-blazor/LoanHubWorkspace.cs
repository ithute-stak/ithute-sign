using IthuteSign.Modern;
namespace IthuteSign.Blazor;
public sealed class LoanHubWorkspace : IDisposable
{
    private LoanHubSession? _session;
    public string? CompanyName { get; private set; }
    public bool LoggedIn => _session?.IsAuthenticated == true;
    public async Task LoginAsync(string phone, string password, string otp)
    {
        Logout();
        var session = new LoanHubSession(new Uri("https://api.loanhub.co.ls/"));
        try
        {
            await session.LoginAsync(phone, password, otp);
            var company = await session.GetCompanyNameAsync();
            _session = session;
            CompanyName = company;
        }
        finally { if (_session != session) session.Dispose(); }
    }
    public Task<IReadOnlyList<CompanyLoanRow>> LoansAsync() =>
        _session?.GetCompanyLoansAsync() ??
        throw new UnauthorizedAccessException("Please log in first.");
    public void Logout()
    {
        _session?.Dispose();
        _session = null;
        CompanyName = null;
    }
    public void Dispose() => Logout();
}
