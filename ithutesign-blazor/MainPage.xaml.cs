using Microsoft.Maui.Controls;
using Microsoft.AspNetCore.Components.WebView.Maui;
namespace IthuteSign.Blazor;
public partial class MainPage : ContentPage
{
    public MainPage()
    {
        InitializeComponent();
    }
    private void OnWebViewInitializing(object? sender, BlazorWebViewInitializingEventArgs e)
    {
        StartupStatus.Text = "IthuteSign • Initializing WebView2…";
    }
    private void OnWebViewInitialized(object? sender, BlazorWebViewInitializedEventArgs e)
    {
        StartupStatus.Text = "IthuteSign • WebView2 initialized; loading Blazor…";
    }
}