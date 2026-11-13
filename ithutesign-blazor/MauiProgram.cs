using Microsoft.Maui.Hosting;
using Microsoft.Maui.Controls.Hosting;
using Microsoft.Extensions.DependencyInjection;
namespace IthuteSign.Blazor;
public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        StartupTrace.Write("MauiProgram.CreateMauiApp entered");
        var builder = MauiApp.CreateBuilder();
        builder.UseMauiApp<App>();
        builder.Services.AddMauiBlazorWebView();
#if DEBUG
        builder.Services.AddBlazorWebViewDeveloperTools();
#endif
        builder.Services.AddSingleton<LoanHubWorkspace>();
        var app = builder.Build();
        StartupTrace.Write("MauiProgram.Build complete");
        return app;
    }
}