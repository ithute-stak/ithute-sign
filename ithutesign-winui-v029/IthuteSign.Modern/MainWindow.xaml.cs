using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using System.IO;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Windows.Storage.Pickers;
using WinRT.Interop;
using Microsoft.Web.WebView2.Core;

namespace IthuteSign.Modern;

public sealed partial class MainWindow : Window
{
    private readonly List<string> _recent = new();
    private LoanHubSession? _loanHubSession;
    private IReadOnlyList<CompanyLoanRow> _companyLoans = Array.Empty<CompanyLoanRow>();
    private bool _loansLoading;
    private CompanyLoanRow? _selectedLoan;

    private async void TestWacom_Click(object sender, RoutedEventArgs e)
    {
        // Hardware diagnostics only. No LoanHub contract authorization or signed-status changes.
        try
        {
            // Prefer the capture executable shipped alongside IthuteSign. Development
            // and machine-wide installations remain supported as fallbacks.
            var candidates = new[]
            {
                Path.Combine(AppContext.BaseDirectory, "wacom-bridge", "STUCapture.exe"),
                Path.Combine(AppContext.BaseDirectory, "STUCapture.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                    "IthuteSign", "wacom-bridge", "STUCapture.exe"),
                Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..",
                    "ithute-sign", "wacom-bridge", "bin", "STUCapture.exe"))
            };
            var exe = candidates.FirstOrDefault(File.Exists);
            if (exe is null)
            {
                WacomDiagnosticStatus.Text = "Wacom capture bridge not found.";
                ShowError("The Wacom capture component is missing. Reinstall IthuteSign with its Wacom bridge, or build the bridge for development.");
                return;
            }
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "IthuteSign", "diagnostics");
            Directory.CreateDirectory(folder);
            var output = Path.Combine(folder, "wacom-test-" + Guid.NewGuid().ToString("N") + ".png");
            var start = new ProcessStartInfo(exe)
            {
                UseShellExecute = false,
                WorkingDirectory = Path.GetDirectoryName(exe)!
            };
            start.ArgumentList.Add(output);
            WacomDiagnosticStatus.Text = "Waiting for Wacom test capture...";
            using var process = Process.Start(start)
                ?? throw new InvalidOperationException("Wacom capture process could not start.");
            using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(3));
            try
            {
                await process.WaitForExitAsync(timeout.Token);
            }
            catch (OperationCanceledException)
            {
                if (!process.HasExited) process.Kill(entireProcessTree: true);
                WacomDiagnosticStatus.Text = "Wacom test timed out. No LoanHub contract was changed.";
                return;
            }
            if (process.ExitCode == 0 && File.Exists(output))
            {
                var bytes = await File.ReadAllBytesAsync(output);
                byte[] signature = { 137, 80, 78, 71, 13, 10, 26, 10 };
                if (bytes.Length < 33 || bytes.Length > 10 * 1024 * 1024
                    || !bytes.AsSpan(0, 8).SequenceEqual(signature)
                    || System.Text.Encoding.ASCII.GetString(bytes, 12, 4) != "IHDR")
                    throw new InvalidDataException("The capture bridge did not produce a valid PNG header.");
                var digest = Convert.ToHexString(SHA256.HashData(bytes));
                WacomDiagnosticStatus.Text = "Hardware test saved locally: " + output
                    + " | SHA-256: " + digest
                    + " | Diagnostic only; no LoanHub contract was signed.";
            }
            else
                WacomDiagnosticStatus.Text = "Hardware test cancelled or failed. No LoanHub contract was changed.";
        }
        catch (Exception ex)
        {
            WacomDiagnosticStatus.Text = "Hardware test failed.";
            ShowError("Wacom diagnostic: " + ex.Message);
        }
    }

    private async void LoanHubLogin_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            LoanHubLoginStatus.Text = "Connecting to LoanHub...";
            _loanHubSession?.Dispose();
            _loanHubSession = null;
            var session = new LoanHubSession(new Uri("https://api.loanhub.co.ls/", UriKind.Absolute));
            try
            {
                var user = await session.LoginAsync(
                    LoanHubPhone.Text, LoanHubPassword.Password, LoanHubOtp.Password);
                var companyName = await session.GetCompanyNameAsync();
                _loanHubSession = session;
                await RefreshCompanyLoansAsync();
                LoanHubLoginStatus.Text =
                    $"Authenticated: {user.Phone} | Company: {companyName}. Signing requires separate workstation and document authorization.";
            }
            finally
            {
                LoanHubPassword.Password = "";
                LoanHubOtp.Password = "";
                if (_loanHubSession != session) session.Dispose();
            }
        }
        catch (Exception ex)
        {
            LoanHubLoginStatus.Text = "Not connected.";
            ShowError("LoanHub login failed: " + ex.Message);
        }
    }

    private async Task RefreshCompanyLoansAsync()
    {
        if (_loanHubSession is null || !_loanHubSession.IsAuthenticated || _loansLoading) return;
        _loansLoading = true;
        CompanyLoansStatus.Text = "Loading company loans...";
        try
        {
            _companyLoans = await _loanHubSession.GetCompanyLoansAsync();
            FilterCompanyLoans();
        }
        catch (Exception ex)
        {
            _companyLoans = Array.Empty<CompanyLoanRow>();
            _selectedLoan = null;
            ReviewSelectedLoanContract.IsEnabled = false;
            SelectedLoanContractStatus.Text = "Loans unavailable. No contract can be retrieved.";
            CompanyLoansList.ItemsSource = null;
            CompanyLoansStatus.Text = "Unable to load company loans: " + ex.Message;
        }
        finally { _loansLoading = false; }
    }

    private void FilterCompanyLoans()
    {
        var search = CompanyLoansSearch.Text?.Trim() ?? "";
        var filtered = _companyLoans.Where(loan =>
            string.IsNullOrEmpty(search) ||
            (loan.FolioNumber?.Contains(search, StringComparison.OrdinalIgnoreCase) ?? false) ||
            (loan.LoanReference?.Contains(search, StringComparison.OrdinalIgnoreCase) ?? false) ||
            (loan.Status?.Contains(search, StringComparison.OrdinalIgnoreCase) ?? false)).ToArray();
        CompanyLoansList.ItemsSource = filtered;
        CompanyLoansStatus.Text = $"Showing {filtered.Length} of {_companyLoans.Count} company loans.";
    }

    private void CompanyLoansSearch_TextChanged(object sender, TextChangedEventArgs e) => FilterCompanyLoans();

    private async void RefreshCompanyLoans_Click(object sender, RoutedEventArgs e) =>
        await RefreshCompanyLoansAsync();

    private void CompanyLoansList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        _selectedLoan = CompanyLoansList.SelectedItem as CompanyLoanRow;
        ReviewSelectedLoanContract.IsEnabled = _selectedLoan is not null;
        if (_selectedLoan is not { } loan)
        {
            CompanyLoanDetails.Text = "Select a loan to review its details.";
            SelectedLoanContractStatus.Text = "No loan selected.";
            return;
        }
        CompanyLoanDetails.Text =
            $"Folio: {loan.FolioNumber ?? "Not supplied"} | Reference: {loan.LoanReference ?? "Not supplied"} | " +
            $"Status: {loan.Status ?? "Not supplied"} | Principal: LSL {loan.Principal:N2} | " +
            $"Total: LSL {loan.TotalRepayable:N2} | Balance: LSL {loan.Balance:N2}" +
            (loan.MaturityDate is null ? "" : $" | Maturity: {loan.MaturityDate:dd MMM yyyy}");
        SelectedLoanContractStatus.Text =
            "Loan selected. Contract retrieval requires a verified, tenant-authorized LoanHub download endpoint. No signing is enabled.";
    }

    private void ReviewSelectedLoanContract_Click(object sender, RoutedEventArgs e)
    {
        if (_selectedLoan is null || _loanHubSession?.IsAuthenticated != true ||
            _loanHubSession.CompanyId != _selectedLoan.CompanyId)
        {
            SelectedLoanContractStatus.Text = "Select an authorized company loan after logging in.";
            return;
        }
        SelectedLoanContractStatus.Text =
            "Contract preview is pending verification of the LoanHub document endpoint. " +
            "No file was downloaded and no signing status was changed.";
    }

    private async void ContractPreflight_Click(object sender, RoutedEventArgs e)
    {
        ContractPreflightStatus.Text = "Checking authorization for National ID document lookup. Signing disabled.";
        if (_loanHubSession is null || !_loanHubSession.IsAuthenticated)
        {
            ContractPreflightStatus.Text = "Log in as an authorized LoanHub employee first. Signing disabled.";
            return;
        }
        if (string.IsNullOrWhiteSpace(ContractReference.Text)
            || ContractReference.Text.Trim().Length > 128)
        {
            ContractPreflightStatus.Text = "Enter the client National ID exactly as registered (up to 128 characters).";
            return;
        }
        if (!Guid.TryParse(WorkstationId.Text.Trim(), out var workstationId))
        {
            ContractPreflightStatus.Text = "Enter the registered workstation UUID. Signing disabled.";
            return;
        }
        try
        {
            using var assignment = await _loanHubSession.GetOperatorAssignmentAsync(workstationId);
            var root = assignment.RootElement;
            bool assigned = root.TryGetProperty("assigned", out var value)
                && value.ValueKind == JsonValueKind.True;
            if (!assigned)
                throw new UnauthorizedAccessException("LoanHub has not confirmed operator assignment.");
            ContractPreflightStatus.Text = "Employee and workstation assignment checked. "
                + "National ID lookup of all unsigned loan documents requires the verified LoanHub backend API. "
                + "No client data was retrieved or changed; signing remains disabled.";
        }
        catch (Exception ex)
        {
            ContractPreflightStatus.Text = "Preflight failed. No contract was fetched or changed. "
                + ex.Message;
        }
    }

    private async void CheckWorkstation_Click(object sender, RoutedEventArgs e)
    {
        WorkstationStatus.Text = "Workstation not verified. Signing disabled.";
        DeviceChallengeStatus.Text = "Complete device proof inside the enrolled local connector. Signing disabled.";
        if (_loanHubSession is null || !_loanHubSession.IsAuthenticated)
        {
            ShowError("Log in to LoanHub before checking this workstation.");
            return;
        }
        if (!Guid.TryParse(WorkstationId.Text.Trim(), out var workstationId))
        {
            ShowError("Enter a valid registered workstation UUID.");
            return;
        }
        try
        {
            using var assignment = await _loanHubSession.GetOperatorAssignmentAsync(workstationId);
            var root = assignment.RootElement;
            bool assigned = root.TryGetProperty("assigned", out var a) && a.ValueKind == JsonValueKind.True;
            bool deviceProofRequired = root.TryGetProperty("device_proof_required", out var d) && d.ValueKind == JsonValueKind.True;
            bool signingAuthorized = root.TryGetProperty("signing_authorized", out var g) && g.ValueKind == JsonValueKind.True;
            if (!assigned)
                throw new UnauthorizedAccessException("LoanHub did not confirm operator assignment.");
            WorkstationStatus.Text = deviceProofRequired
                ? "Operator assigned. Enrolled-device proof and signing authorization still required."
                : signingAuthorized
                    ? "Operator assigned. Additional document-specific signing authorization is still required."
                    : "Operator assigned. Signing remains disabled pending further authorization.";
        }
        catch (Exception ex)
        {
            WorkstationStatus.Text = "Workstation verification failed. Signing disabled.";
            ShowError("Workstation access denied: " + ex.Message);
        }
    }

    private async void CheckLocalConnector_Click(object sender, RoutedEventArgs e)
    {
        LocalConnectorStatus.Text = "Checking local connector. Signing disabled.";
        try
        {
            // Fixed loopback host; no user-controlled URL or auth credentials.
            // A reachable HTML page is NOT proof of employee authentication,
            // registered workstation identity or signing authorization.
            using var handler = new HttpClientHandler
            {
                AllowAutoRedirect = false,
                UseCookies = false,
                UseProxy = false
            };
            using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(3) };
            using var request = new HttpRequestMessage(HttpMethod.Get, "http://127.0.0.1:8767/");
            using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
            var contentType = response.Content.Headers.ContentType?.MediaType;
            if (response.StatusCode != System.Net.HttpStatusCode.OK ||
                !string.Equals(contentType, "text/html", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Unexpected local connector response.");
            LocalConnectorStatus.Text =
                "Local workstation desk is reachable. Open it to log in and complete device verification. Signing remains disabled.";
        }
        catch
        {
            LocalConnectorStatus.Text =
                "Local workstation desk unavailable. Start the approved Go connector in --pc-ui mode. Signing disabled.";
        }
    }

    private Process? _ownedWorkstationDesk;

    private async Task EnsureWorkstationDeskRunningAsync()
    {
        // Only start a connector shipped with the application; never execute a
        // user-supplied path or pass credentials through process arguments.
        var executable = Path.Combine(AppContext.BaseDirectory, "wacom-connector",
            "loanhub-wacom-connector.exe");
        if (!File.Exists(executable))
            return; // Existing installed connector may already be running.

        using var handler = new HttpClientHandler
        {
            AllowAutoRedirect = false, UseCookies = false, UseProxy = false
        };
        using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(2) };
        try
        {
            using var response = await http.GetAsync("http://127.0.0.1:8767/",
                HttpCompletionOption.ResponseHeadersRead);
            if (response.IsSuccessStatusCode)
                return;
        }
        catch (HttpRequestException) { }
        catch (TaskCanceledException) { }

        if (_ownedWorkstationDesk is { HasExited: false })
            return;
        var start = new ProcessStartInfo(executable)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = Path.GetDirectoryName(executable)!
        };
        start.ArgumentList.Add("--pc-ui");
        start.ArgumentList.Add("--loanhub-origin=https://api.loanhub.co.ls");
        _ownedWorkstationDesk = Process.Start(start)
            ?? throw new InvalidOperationException("Packaged workstation desk could not start.");
        // Startup is asynchronous. Readiness is checked independently below;
        // process launch never means workstation authorization or signing success.
        for (var attempt = 0; attempt < 12; attempt++)
        {
            await Task.Delay(250);
            if (_ownedWorkstationDesk.HasExited)
                throw new InvalidOperationException("Workstation desk exited during startup.");
            try
            {
                using var response = await http.GetAsync("http://127.0.0.1:8767/",
                    HttpCompletionOption.ResponseHeadersRead);
                if (response.StatusCode == System.Net.HttpStatusCode.OK &&
                    response.Content.Headers.ContentType?.MediaType == "text/html")
                    return;
            }
            catch (HttpRequestException) { }
            catch (TaskCanceledException) { }
        }
        throw new InvalidOperationException("Workstation desk did not become ready.");
    }

    private bool _embeddedDeskReady;

    private async void OpenEmbeddedWorkstationDesk_Click(object sender, RoutedEventArgs e)
    {
        // The existing Go connector owns the browser session, CSRF protection,
        // employee login, workstation private key, and Wacom SDK operations.
        // No WinUI credentials or bearer tokens are forwarded to localhost.
        try
        {
            await EnsureWorkstationDeskRunningAsync();
            using var handler = new HttpClientHandler
            {
                AllowAutoRedirect = false, UseCookies = false, UseProxy = false
            };
            using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(3) };
            using var request = new HttpRequestMessage(HttpMethod.Get, "http://127.0.0.1:8767/");
            using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
            if (response.StatusCode != System.Net.HttpStatusCode.OK ||
                !string.Equals(response.Content.Headers.ContentType?.MediaType, "text/html",
                    StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Approved local connector is unavailable.");

            await EmbeddedDesk.EnsureCoreWebView2Async();
            if (!_embeddedDeskReady)
            {
                EmbeddedDesk.CoreWebView2.NewWindowRequested += (_, args) => args.Handled = true;
                EmbeddedDesk.CoreWebView2.DownloadStarting += (_, args) => args.Cancel = true;
                EmbeddedDesk.CoreWebView2.PermissionRequested += (_, args) =>
                    args.State = CoreWebView2PermissionState.Deny;
                EmbeddedDesk.CoreWebView2.Settings.AreDevToolsEnabled = false;
                EmbeddedDesk.CoreWebView2.Settings.AreHostObjectsAllowed = false;
                EmbeddedDesk.CoreWebView2.Settings.IsWebMessageEnabled = false;
                _embeddedDeskReady = true;
            }
            EmbeddedDeskPanel.Visibility = Visibility.Visible;
            EmbeddedDesk.Source = new Uri("http://127.0.0.1:8767/");
            EmbeddedDeskStatus.Text =
                "LoanHub connector desk opened locally. Sign in inside this desk and complete enrolled-device verification. Evidence review is not contract signing.";
        }
        catch (Exception ex)
        {
            EmbeddedDeskPanel.Visibility = Visibility.Collapsed;
            EmbeddedDeskStatus.Text = "Local signing desk unavailable. Signing disabled.";
            ShowError("Start the approved Go Wacom connector with --pc-ui and enrolled workstation keys. " + ex.Message);
        }
    }

    private void EmbeddedDesk_NavigationStarting(WebView2 sender, CoreWebView2NavigationStartingEventArgs args)
    {
        // Block navigation to any external site, loopback aliases, or other ports.
        // The embedded page uses the Go connector's existing cookie and CSRF session.
        if (!Uri.TryCreate(args.Uri, UriKind.Absolute, out var target) ||
            target.Scheme != Uri.UriSchemeHttp ||
            target.Host != "127.0.0.1" || target.Port != 8767 ||
            !string.IsNullOrEmpty(target.UserInfo) || !string.IsNullOrEmpty(target.Fragment))
            args.Cancel = true;
    }

    private void OpenLocalWorkstationDesk_Click(object sender, RoutedEventArgs e)
    {
        // Fixed loopback address only. Do not forward the WinUI bearer token,
        // workstation key, company context, or a server-issued challenge.
        // The Go connector has its own cookie/CSRF and employee login.
        try
        {
            Process.Start(new ProcessStartInfo("http://127.0.0.1:8767/")
            {
                UseShellExecute = true
            });
        }
        catch
        {
            ShowError("Could not open the local workstation desk. Start the approved LoanHub Wacom connector in --pc-ui mode first.");
        }
    }

    private void LoanHubLogout_Click(object sender, RoutedEventArgs e)
    {
        _loanHubSession?.Dispose();
        _loanHubSession = null;
        _companyLoans = Array.Empty<CompanyLoanRow>();
        CompanyLoansList.ItemsSource = null;
        CompanyLoanDetails.Text = "";
        CompanyLoansStatus.Text = "Log in to load company loans.";
        LoanHubPassword.Password = "";
        LoanHubOtp.Password = "";
        LoanHubLoginStatus.Text = "Logged out. LoanHub signing is unavailable.";
        WorkstationStatus.Text = "Workstation not verified. Signing disabled.";
        DeviceChallengeStatus.Text = "Device proof not verified. Signing disabled.";
    }

    private string? _selectedPath;
    private bool _previewReady;
    private readonly string _settingsPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "IthuteSign", "modern-settings.json");
    private sealed class SettingsData
    {
        public string? SignerExecutable { get; set; }
        public List<string> RecentFiles { get; set; } = new();
    }
    private SettingsData _settings = new();

    public MainWindow()
    {
        InitializeComponent();
        LoadSettings();
    }

    private async void ChooseDocument_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var picker = new FileOpenPicker();
            InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
            picker.FileTypeFilter.Add(".pdf");
            picker.FileTypeFilter.Add(".docx");
            picker.FileTypeFilter.Add(".doc");
            var file = await picker.PickSingleFileAsync();
            if (file is null) return;
            _selectedPath = file.Path;
            SelectedDocument.Text = _selectedPath;
            RefreshDocumentDetails();
            await PreviewDocumentAsync();
            _recent.Remove(_selectedPath);
            _recent.Insert(0, _selectedPath);
            if (_recent.Count > 8) _recent.RemoveAt(_recent.Count - 1);
            SaveSettings();
            RecentFiles.ItemsSource = null;
            RecentFiles.ItemsSource = _recent.ToArray();
        }
        catch (Exception ex)
        {
            ShowError("Unable to open document picker: " + ex.Message);
        }
    }

    private void RecentFiles_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (RecentFiles.SelectedItem is string path)
        {
            _selectedPath = path;
            SelectedDocument.Text = path;
            RefreshDocumentDetails();
        }
    }

    private void ThemeSelector_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (Content is not FrameworkElement root || ThemeSelector is null) return;
        root.RequestedTheme = ThemeSelector.SelectedIndex switch
        {
            1 => ElementTheme.Light,
            2 => ElementTheme.Dark,
            _ => ElementTheme.Default
        };
    }

    private void LaunchLegacy_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var candidates = new[]
            {
                System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "IthuteSign", "IthuteSign.exe"),
                @"C:\ithute-sign\dist\IthuteSign\IthuteSign.exe"
            };
            var custom = SignerPath.Text.Trim().Trim('"');
            if (custom.Length > 0 && !Path.IsPathFullyQualified(custom))
            {
                ShowError("Signing engine path must be absolute.");
                return;
            }
            var exe = custom.Length > 0 ? custom : candidates.FirstOrDefault(File.Exists);
            if (exe is not null && !File.Exists(exe))
            {
                ShowError("Signing engine not found at: " + exe);
                return;
            }
            if (exe is null)
            {
                ShowError("Classic IthuteSign not found. Install v0.28 or update its path in MainWindow.xaml.cs.");
                return;
            }
            var start = new ProcessStartInfo(exe) { UseShellExecute = false };
            if (_selectedPath is not null)
            {
                if (!System.IO.File.Exists(_selectedPath))
                {
                    ShowError("Selected document no longer exists. Choose it again.");
                    return;
                }
                start.ArgumentList.Add("--open");
                start.ArgumentList.Add(_selectedPath);
            }
            Process.Start(start);
            StatusBar.Severity = InfoBarSeverity.Success;
            StatusBar.Message = _selectedPath is null
                ? "Signing application launched. Choose a document there."
                : "Signing application launched with your selected document.";
            StatusBar.IsOpen = true;
        }
        catch (Exception ex)
        {
            ShowError("Unable to launch signing application: " + ex.Message);
        }
    }

    private void RefreshDocumentDetails()
    {
        _previewReady = false;
        if (_selectedPath is null || !File.Exists(_selectedPath))
        {
            DocumentDetails.Text = "Select a local document to view its details.";
            return;
        }
        try
        {
            var info = new FileInfo(_selectedPath);
            var type = info.Extension.ToUpperInvariant();
            DocumentDetails.Text = $"{type}  •  {info.Length:N0} bytes  •  Modified {info.LastWriteTime:g}";
        }
        catch (Exception ex)
        {
            DocumentDetails.Text = "Document details unavailable: " + ex.Message;
        }
    }

    private async void PreviewSelected_Click(object sender, RoutedEventArgs e)
    {
        await PreviewDocumentAsync();
    }

    // The preview is deliberately read-only and restricted to the selected local PDF.
    private async Task PreviewDocumentAsync()
    {
        if (_selectedPath is null || !File.Exists(_selectedPath))
        {
            PreviewHint.Text = "Choose an existing PDF file to preview.";
            return;
        }
        if (!string.Equals(Path.GetExtension(_selectedPath), ".pdf", StringComparison.OrdinalIgnoreCase))
        {
            PreviewHint.Text = "Word preview is not supported here. Launch the signing app for DOC/DOCX.";
            return;
        }
        try
        {
            // WebView2 renders a local PDF; no document is uploaded to a server.
            await PdfPreview.EnsureCoreWebView2Async();
            if (!_previewReady)
            {
                PdfPreview.CoreWebView2.NewWindowRequested += (_, args) => args.Handled = true;
                PdfPreview.CoreWebView2.DownloadStarting += (_, args) => args.Cancel = true;
                _previewReady = true;
            }
            PdfPreview.Source = new Uri(Path.GetFullPath(_selectedPath));
            PreviewHint.Text = "Local PDF preview: " + Path.GetFileName(_selectedPath);
        }
        catch (Exception ex)
        {
            ShowError("PDF preview unavailable: " + ex.Message);
        }
    }

    private void PdfPreview_NavigationStarting(WebView2 sender, CoreWebView2NavigationStartingEventArgs args)
    {
        // Prevent links inside documents from opening network resources in the embedded preview.
        if (_selectedPath is null || !string.Equals(Path.GetExtension(_selectedPath), ".pdf", StringComparison.OrdinalIgnoreCase))
        {
            args.Cancel = true;
            return;
        }
        var allowed = new Uri(Path.GetFullPath(_selectedPath)).AbsoluteUri;
        if (!string.Equals(args.Uri, allowed, StringComparison.OrdinalIgnoreCase))
            args.Cancel = true;
    }

    private void LoadSettings()
    {
        try
        {
            if (File.Exists(_settingsPath))
                _settings = JsonSerializer.Deserialize<SettingsData>(File.ReadAllText(_settingsPath)) ?? new();
            SignerPath.Text = _settings.SignerExecutable ?? "";
            _recent.AddRange(_settings.RecentFiles.Where(File.Exists).Distinct(StringComparer.OrdinalIgnoreCase).Take(8));
            RecentFiles.ItemsSource = _recent.ToArray();
        }
        catch (Exception ex)
        {
            ShowError("Could not load local preferences: " + ex.Message);
        }
    }

    private void SaveSettings()
    {
        try
        {
            _settings.SignerExecutable = SignerPath.Text.Trim();
            _settings.RecentFiles = _recent.ToList();
            Directory.CreateDirectory(Path.GetDirectoryName(_settingsPath)!);
            var tmp = _settingsPath + ".tmp";
            File.WriteAllText(tmp, JsonSerializer.Serialize(_settings));
            File.Move(tmp, _settingsPath, true);
        }
        catch (Exception ex)
        {
            ShowError("Could not save local preferences: " + ex.Message);
        }
    }

    private void SaveSignerPath_Click(object sender, RoutedEventArgs e)
    {
        var candidate = SignerPath.Text.Trim().Trim('"');
        if (candidate.Length > 0 && (!Path.IsPathFullyQualified(candidate) || !File.Exists(candidate) ||
            !string.Equals(Path.GetExtension(candidate), ".exe", StringComparison.OrdinalIgnoreCase)))
        {
            ShowError("Choose an existing absolute path to IthuteSign.exe, or leave the field blank.");
            return;
        }
        SignerPath.Text = candidate;
        SaveSettings();
        StatusBar.Severity = InfoBarSeverity.Success;
        StatusBar.Message = "Local signing engine preference saved.";
        StatusBar.IsOpen = true;
    }

    private void ClearRecent_Click(object sender, RoutedEventArgs e)
    {
        _recent.Clear();
        RecentFiles.ItemsSource = Array.Empty<string>();
        _selectedPath = null;
        SelectedDocument.Text = "No document selected";
        RefreshDocumentDetails();
        SaveSettings();
    }

    private void ShowError(string message)
    {
        StatusBar.Severity = InfoBarSeverity.Error;
        StatusBar.Message = message;
        StatusBar.IsOpen = true;
    }
}
