using Microsoft.Maui.Controls;
namespace IthuteSign.Blazor;
public partial class MainPage : ContentPage
{
    public MainPage()
    {
        StartupTrace.Write("MainPage constructor entered");
        InitializeComponent();
        StartupTrace.Write("MainPage XAML initialized");
        StartupStatus.Text = "IthuteSign • Native window loaded — starting Blazor WebView…";
    }
}