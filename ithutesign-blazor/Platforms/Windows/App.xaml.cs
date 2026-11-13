using Microsoft.Maui;
using Microsoft.Maui.Hosting;
namespace IthuteSign.Blazor.WinUI;
public partial class App : MauiWinUIApplication
{
    public App()
    {
        StartupTrace.Write("Windows App constructor entered");
        UnhandledException += (_, e) => StartupTrace.Write("WinUI unhandled exception: " + e.Exception);
        InitializeComponent();
        StartupTrace.Write("Windows App InitializeComponent complete");
    }
    protected override MauiApp CreateMauiApp()
    {
        StartupTrace.Write("CreateMauiApp entered");
        var app = MauiProgram.CreateMauiApp();
        StartupTrace.Write("CreateMauiApp complete");
        return app;
    }
}