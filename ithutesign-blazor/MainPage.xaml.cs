using Microsoft.Maui.Controls;
namespace IthuteSign.Blazor;
public partial class MainPage : ContentPage
{
    public MainPage()
    {
        InitializeComponent();
        StartupStatus.Text = "IthuteSign • Native window loaded — starting Blazor WebView…";
    }
}
