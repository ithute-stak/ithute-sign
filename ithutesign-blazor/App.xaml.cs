using Microsoft.Maui.Controls;
using Microsoft.Maui.Storage;
namespace IthuteSign.Blazor;
public partial class App : Application
{
    public App()
    {
        StartupTrace.Write("MAUI App constructor entered");
#if WINDOWS
        var dataFolder = Path.Combine(FileSystem.AppDataDirectory, "WebView2");
        Directory.CreateDirectory(dataFolder);
        Environment.SetEnvironmentVariable("WEBVIEW2_USER_DATA_FOLDER", dataFolder);
        StartupTrace.Write("WebView2 data directory configured");
#endif
        InitializeComponent();
        StartupTrace.Write("MAUI App XAML initialized");
        MainPage = new MainPage();
        StartupTrace.Write("MainPage assigned");
    }
}