namespace IthuteSign.Blazor;
internal static class StartupTrace
{
    private static readonly object Gate = new();
    internal static readonly string LogPath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "IthuteSign", "startup.log");

    internal static void Write(string message)
    {
        try
        {
            lock (Gate)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(LogPath)!);
                File.AppendAllText(LogPath,
                    DateTimeOffset.Now.ToString("O") + " " + message + Environment.NewLine);
            }
        }
        catch { /* Diagnostics must never prevent startup. */ }
    }
}
