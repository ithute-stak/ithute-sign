using System;
using System.Drawing;
using System.Drawing.Imaging;
using IthuteSignWacom;
internal static class BrandingSmoke
{
    private static int Main()
    {
        foreach (var mode in new[] { "welcome", "thanks" })
        {
            using (var bitmap = TabletBranding.Render(mode, 800, 480, null))
            {
                if (bitmap.Width != 800 || bitmap.Height != 480) return 1;
                if (bitmap.GetPixel(10, 10).A != 255) return 2;
                bitmap.Save(mode + ".png", ImageFormat.Png);
            }
        }
        try { using (var bitmap = TabletBranding.Render("invalid", 800, 480, null)) { } }
        catch (ArgumentException) { return 0; }
        return 3;
    }
}