using System.Diagnostics;
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

    private async void LoanHubLogin_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            LoanHubLoginStatus.Text = "Connecting to LoanHub...";
            _loanHubSession?.Dispose();
            _loanHubSession = null;
            var session = new LoanHubSession(new Uri(LoanHubUrl.Text.Trim(), UriKind.Absolute));
            try
            {
                var user = await session.LoginAsync(
                    LoanHubPhone.Text, LoanHubPassword.Password, LoanHubOtp.Password);
                _loanHubSession = session;
                LoanHubLoginStatus.Text =
                    $"Authenticated: {user.Phone}. Signing requires separate workstation and document authorization.";
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

    private async void CheckWorkstation_Click(object sender, RoutedEventArgs e)
    {
        WorkstationStatus.Text = "Workstation not verified. Signing disabled.";
        DeviceChallengeStatus.Text = "Device proof not verified. Signing disabled.";
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

    private async void RequestDeviceChallenge_Click(object sender, RoutedEventArgs e)
    {
        DeviceChallengeStatus.Text = "Device proof not verified. Signing disabled.";
        if (_loanHubSession is null || !_loanHubSession.IsAuthenticated ||
            !Guid.TryParse(WorkstationId.Text.Trim(), out var workstationId))
        {
            ShowError("Log in and enter a registered workstation ID first.");
            return;
        }
        try
        {
            var challenge = await _loanHubSession.RequestDeviceChallengeAsync(workstationId);
            // Ensure our transcript exactly matches LoanHub's proof protocol.
            // Signing and submission must be done by the enrolled local bridge.
            _ = DeviceProofMessage.Create(challenge, challenge.CompanyId, challenge.EmployeeUserId);
            // Do not expose nonce or credentials in UI/logs. The enrolled
            // workstation bridge must sign and submit proof in a later phase.
            DeviceChallengeStatus.Text =
                $"Challenge issued (expires {challenge.ExpiresAt.LocalDateTime:t}). " +
                "Device-key proof is still required. Signing disabled.";
        }
        catch (Exception ex)
        {
            DeviceChallengeStatus.Text = "Device challenge unavailable. Signing disabled.";
            ShowError("Device challenge failed: " + ex.Message);
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
