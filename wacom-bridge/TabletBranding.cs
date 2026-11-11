using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;

namespace IthuteSignWacom
{
    /// <summary>
    /// Builds the STU-540 welcome and completion screens at tablet resolution.
    /// Rendering a bitmap is not equivalent to transmitting it to the tablet.
    /// </summary>
    internal static class TabletBranding
    {
        internal static Bitmap Render(string mode, int width, int height, string logoPath)
        {
            if (mode != "welcome" && mode != "thanks")
                throw new ArgumentException("Unknown screen", "mode");
            if (width < 100 || height < 80 || width > 4096 || height > 4096)
                throw new ArgumentOutOfRangeException("width", "Invalid tablet dimensions");

            var image = new Bitmap(width, height, System.Drawing.Imaging.PixelFormat.Format24bppRgb);
            using (var graphics = Graphics.FromImage(image))
            using (var background = new LinearGradientBrush(
                new Rectangle(0, 0, width, height),
                Color.FromArgb(12, 31, 60), Color.FromArgb(26, 77, 123), 30f))
            using (var titleFont = new Font("Segoe UI", Math.Max(14, height * .095f), FontStyle.Bold, GraphicsUnit.Pixel))
            using (var captionFont = new Font("Segoe UI", Math.Max(10, height * .052f), FontStyle.Regular, GraphicsUnit.Pixel))
            using (var accent = new SolidBrush(Color.FromArgb(89, 207, 216)))
            {
                graphics.SmoothingMode = SmoothingMode.AntiAlias;
                graphics.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
                graphics.FillRectangle(background, 0, 0, width, height);
                graphics.FillRectangle(accent, 0, height - Math.Max(4, height / 45), width, Math.Max(4, height / 45));

                float top = height * .11f;
                if (!String.IsNullOrWhiteSpace(logoPath) && File.Exists(logoPath))
                {
                    using (var logo = Image.FromFile(logoPath))
                    {
                        float boxWidth = width * .24f, boxHeight = height * .30f;
                        float scale = Math.Min(boxWidth / logo.Width, boxHeight / logo.Height);
                        float w = logo.Width * scale, h = logo.Height * scale;
                        graphics.DrawImage(logo, (width - w) / 2f, top, w, h);
                        top += boxHeight + height * .04f;
                    }
                }
                else
                {
                    top += height * .17f;
                }
                string headline = mode == "welcome" ? "Welcome to IthuteSign" : "Thank you for signing";
                string caption = mode == "welcome" ? "Secure document signing" : "Your signature was captured";
                using (var format = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
                {
                    graphics.DrawString(headline, titleFont, Brushes.White,
                        new RectangleF(width * .05f, top, width * .90f, height * .18f), format);
                    graphics.DrawString(caption, captionFont, Brushes.WhiteSmoke,
                        new RectangleF(width * .05f, top + height * .18f, width * .90f, height * .12f), format);
                }
            }
            return image;
        }
    }
}
