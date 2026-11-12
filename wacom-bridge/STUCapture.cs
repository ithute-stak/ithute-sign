using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Windows.Forms;
using wgssSTU;
using Rectangle = System.Drawing.Rectangle;

namespace IthuteSignWacom
{
    internal static class STUCapture
    {
        [STAThread]
        private static int Main(string[] args)
        {
            if (args.Length != 1) { Console.Error.WriteLine("Expected --probe or output PNG path."); return 12; }
            if (args[0] == "--probe") return Probe();
            if (args[0] == "--welcome" || args[0] == "--thanks")
            {
                Console.Error.WriteLine("Tablet display command is pending hardware validation.");
                return 12;
            }
            if (args[0].StartsWith("--")) return 12;
            try
            {
                Application.EnableVisualStyles();
                using (var form = new SignatureForm(args[0]))
                {
                    Application.Run(form);
                    return form.Saved ? 0 : 1;
                }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex.Message); return 13; }
        }

        private static int Probe()
        {
            try
            {
                var devices = new UsbDevices();
                if (devices.Count == 0) { Console.Error.WriteLine("No STU device detected."); return 10; }
                var tablet = new Tablet();
                try
                {
                    var result = tablet.usbConnect(devices[0], true);
                    if (result.value != 0) { Console.Error.WriteLine("USB connection failed: " + result.value); return 11; }
                    var cap = tablet.getCapability();
                    if (cap == null || cap.tabletMaxX == 0 || cap.tabletMaxY == 0) return 11;
                    Console.WriteLine("Wacom STU device connected.");
                    return 0;
                }
                finally { try { tablet.disconnect(); } catch { } }
            }
            catch (Exception ex) { Console.Error.WriteLine("Wacom SDK/driver: " + ex.Message); return 11; }
        }
    }

    internal sealed class InkSample
    {
        internal float X, Y;
        internal bool Down;
    }

    internal sealed class SignatureForm : Form
    {
        private readonly string destination;
        private readonly List<InkSample> ink = new List<InkSample>();
        private readonly Panel preview = new Panel();
        private readonly FlowLayoutPanel connectionBar = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 40 };
        private readonly Label connectionStatus = new Label { AutoSize = true, Text = "Not checked", Padding = new Padding(8, 9, 0, 0) };
        private readonly Label diagnostics = new Label { Dock = DockStyle.Bottom, Height = 24, Text = "Tablet: connecting... | Pen events: 0 | Contact samples: 0" };
        private int eventCount;
        private int contactCount;
        private readonly Timer penWatchdog = new Timer { Interval = 10000 };
        private DateTime connectedAt;
        private bool penWarningShown;
        private Tablet tablet;
        private ITabletEvents2_onPenDataEventHandler penDataHandler;
        private ICapability capability;
        private bool previousDown;
        internal bool Saved { get; private set; }

        internal SignatureForm(string path)
        {
            destination = Path.GetFullPath(path);
            Text = "IthuteSign — Wacom STU signing";
            Width = 850; Height = 410;
            var header = new Label { Dock = DockStyle.Top, Height = 42,
                Text = "Sign on the Wacom tablet. Review your handwriting below." };
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 48 };
            var detect = new Button { Text = "Detect tablet", Width = 120 };
            var reconnect = new Button { Text = "Connect / Reconnect", Width = 155 };
            detect.Click += (s, e) => DetectTablet();
            reconnect.Click += (s, e) => Connect();
            connectionBar.Controls.Add(detect);
            connectionBar.Controls.Add(reconnect);
            connectionBar.Controls.Add(connectionStatus);
            var clear = new Button { Text = "Clear", Width = 110 };
            var accept = new Button { Text = "Accept signature", Width = 160 };
            var cancel = new Button { Text = "Cancel", Width = 110 };
            clear.Click += (s, e) => { ink.Clear(); preview.Invalidate(); };
            accept.Click += (s, e) => Save();
            cancel.Click += (s, e) => Close();
            buttons.Controls.Add(clear); buttons.Controls.Add(accept); buttons.Controls.Add(cancel);
            preview.Dock = DockStyle.Fill; preview.BackColor = Color.White;
            preview.Paint += (s, e) => DrawInk(e.Graphics, preview.ClientRectangle, ink);
            Controls.Add(preview); Controls.Add(diagnostics); Controls.Add(connectionBar); Controls.Add(header); Controls.Add(buttons);
            penWatchdog.Tick += (s, e) => CheckPenStream();
            Shown += (s, e) => Connect();
            FormClosing += (s, e) => Disconnect();
        }

        private void CheckPenStream()
        {
            if (tablet == null) { penWatchdog.Stop(); return; }
            if (System.Threading.Interlocked.CompareExchange(ref eventCount, 0, 0) == 0 && !penWarningShown && (DateTime.UtcNow - connectedAt).TotalSeconds >= 10)
            {
                penWarningShown = true;
                connectionStatus.Text = "USB connected; no pen reports received — check SDK event stream";
            }
        }

        private void DetectTablet()
        {
            try
            {
                Disconnect();
                var devices = new UsbDevices();
                connectionStatus.Text = devices.Count == 0
                    ? "No Wacom STU device detected"
                    : "Detected " + devices.Count + " STU device(s) — click Connect";
                diagnostics.Text = "Tablet: disconnected | Pen events: 0 | Contact samples: 0";
            }
            catch (Exception ex)
            {
                connectionStatus.Text = "Detection failed: " + ex.Message;
            }
        }

        private void Connect()
        {
            Disconnect();
            eventCount = 0;
            contactCount = 0;
            penWarningShown = false;
            penWatchdog.Stop();
            ink.Clear();
            preview.Invalidate();
            connectionStatus.Text = "Connecting...";

            try
            {
                var devices = new UsbDevices();
                if (devices.Count == 0) throw new InvalidOperationException("No Wacom STU tablet connected.");
                tablet = new Tablet();
                var result = tablet.usbConnect(devices[0], true);
                if (result.value != 0) throw new InvalidOperationException("STU USB error: " + result.value);
                capability = tablet.getCapability();
                if (capability == null || capability.tabletMaxX == 0 || capability.tabletMaxY == 0)
                    throw new InvalidOperationException("Invalid STU tablet capability.");
                // Keep the COM event delegate rooted for the entire connection lifetime.
                penDataHandler = new ITabletEvents2_onPenDataEventHandler(OnPenData);
                tablet.onPenData += penDataHandler;
                tablet.setInkingMode(0x01);
                diagnostics.Text = "Tablet: connected | Pen events: 0 | Contact samples: 0";
                connectionStatus.Text = "Connected — waiting for pen input";
                connectedAt = DateTime.UtcNow;
                penWatchdog.Start();
            }
            catch (Exception ex)
            {
                connectionStatus.Text = "Connection failed: " + ex.Message;
                Disconnect();
                MessageBox.Show(ex.Message, "Wacom connection error");
            }
        }

        private void OnPenData(IPenData point)
        {
            // Count callbacks before filtering, so zero means no callbacks reached this handler.
            System.Threading.Interlocked.Increment(ref eventCount);
            if (capability == null || IsDisposed || !IsHandleCreated) return;
            float x = Math.Max(0f, Math.Min(1f, (float)point.x / capability.tabletMaxX));
            float y = Math.Max(0f, Math.Min(1f, (float)point.y / capability.tabletMaxY));
            bool down = point.sw != 0;
            try
            {
                BeginInvoke(new Action(() =>
                {
                    if (IsDisposed) return;
                    // Pen-up is a stroke boundary. Do not connect separate strokes.
                    ink.Add(new InkSample { X = x, Y = y, Down = down });
                    if (down) contactCount++;
                    connectionStatus.Text = "Connected — receiving pen data";
                    penWatchdog.Stop();
                    diagnostics.Text = "Tablet: connected | Pen events: " + System.Threading.Interlocked.CompareExchange(ref eventCount, 0, 0) + " | Contact samples: " + contactCount;
                    previousDown = down;
                    preview.Invalidate();
                }));
            }
            catch (InvalidOperationException) { } // Includes ObjectDisposedException
        }

        private static void DrawInk(Graphics g, Rectangle rect, IList<InkSample> samples)
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (var pen = new Pen(Color.FromArgb(18, 46, 88), 3f))
            {
                pen.StartCap = LineCap.Round; pen.EndCap = LineCap.Round;
                PointF? previous = null;
                foreach (var sample in samples)
                {
                    if (!sample.Down) { previous = null; continue; }
                    var p = new PointF(rect.X + sample.X * rect.Width, rect.Y + sample.Y * rect.Height);
                    if (previous.HasValue) g.DrawLine(pen, previous.Value, p);
                    else g.FillEllipse(Brushes.DarkBlue, p.X - 1, p.Y - 1, 2, 2);
                    previous = p;
                }
            }
        }

        private void Save()
        {
            int count = 0;
            foreach (var sample in ink) if (sample.Down) count++;
            if (count < 4) { MessageBox.Show("Please sign before accepting."); return; }
            using (var image = new Bitmap(800, 360, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(image))
                {
                    g.Clear(Color.Transparent);
                    DrawInk(g, new Rectangle(10, 10, 780, 340), ink);
                }
                var bounds = InkBounds(image);
                if (bounds.IsEmpty) { MessageBox.Show("No signature ink found."); return; }
                using (var cropped = image.Clone(bounds, image.PixelFormat))
                {
                    string folder = Path.GetDirectoryName(destination);
                    if (!Directory.Exists(folder)) Directory.CreateDirectory(folder);
                    // Write to temporary file first; never leave a partial signature.
                    string temporary = destination + "." + Guid.NewGuid().ToString("N") + ".tmp";
                    try
                    {
                        cropped.Save(temporary, ImageFormat.Png);
                        if (File.Exists(destination)) throw new IOException("Signature output already exists.");
                        File.Move(temporary, destination);
                    }
                    finally { if (File.Exists(temporary)) File.Delete(temporary); }
                }
            }
            Saved = true;
            Close();
        }

        private static Rectangle InkBounds(Bitmap image)
        {
            int left = image.Width, top = image.Height, right = -1, bottom = -1;
            for (int y = 0; y < image.Height; y++)
                for (int x = 0; x < image.Width; x++)
                    if (image.GetPixel(x, y).A != 0)
                    {
                        left = Math.Min(left, x); top = Math.Min(top, y);
                        right = Math.Max(right, x); bottom = Math.Max(bottom, y);
                    }
            if (right < 0) return Rectangle.Empty;
            return Rectangle.FromLTRB(Math.Max(0, left - 8), Math.Max(0, top - 8),
                Math.Min(image.Width, right + 9), Math.Min(image.Height, bottom + 9));
        }

        private void Disconnect()
        {
            penWatchdog.Stop();
            if (tablet == null) return;
            try { if (penDataHandler != null) tablet.onPenData -= penDataHandler; } catch { }
            penDataHandler = null;
            try { tablet.setInkingMode(0x00); } catch { }
            try { tablet.disconnect(); } catch { }
            tablet = null;
        }
    }
}
