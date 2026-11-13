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
