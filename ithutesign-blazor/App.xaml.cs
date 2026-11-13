using Microsoft.Maui.Controls;
using Microsoft.Maui.Storage;
namespace IthuteSign.Blazor;
public partial class App : Application
{
    public App()
    {
#if WINDOWS
        var dataFolder = Path.Combine(FileSystem.AppDataDirectory, "WebView2");
        Directory.CreateDirectory(dataFolder);
        Environment.SetEnvironmentVariable("WEBVIEW2_USER_DATA_FOLDER", dataFolder);
#endif
        InitializeComponent();
        MainPage = new MainPage();
    }
}