import com.WacomGSS.STU.*;
import com.WacomGSS.STU.Protocol.*;
import javax.imageio.ImageIO;
import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.awt.geom.*;
import java.awt.image.BufferedImage;
import java.lang.reflect.Proxy;
import java.nio.file.*;
import java.util.*;
import java.util.List;

/** Linux STU capture bridge. Exit 0 success, 10 no device, 11 SDK error, 13 failure. */
public final class STUCapture {
    private static final int W = 800, H = 480;
    private final List<List<Point2D.Double>> strokes = new ArrayList<>();
    private List<Point2D.Double> current;
    private volatile boolean accepted;
    private volatile boolean cancelled;
    private Tablet tablet;
    private int maxX, maxY;
    private JPanel canvas;
    private volatile JDialog signingDialog;
    private volatile boolean deviceControls;
    private boolean buttonDown;
    private int screenWidth, screenHeight;

    private synchronized void pen(PenData data) {
        if (cancelled || accepted) return;
        boolean down = data.getSw() != 0 && data.getPressure() > 0;
        // Device buttons occupy the bottom strip; never add their touches to signature ink.
        int sx = (int)Math.round(data.getX() * (screenWidth - 1.0) / maxX);
        int sy = (int)Math.round(data.getY() * (screenHeight - 1.0) / maxY);
        if (deviceControls && (buttonDown || sy >= screenHeight * 0.83)) {
            if (down && !buttonDown && sy >= screenHeight * 0.83) {
                buttonDown = true;
                final int action = sx < screenWidth / 3 ? 0 : sx < screenWidth * 2 / 3 ? 1 : 2;
                SwingUtilities.invokeLater(() -> {
                    if (signingDialog == null || !signingDialog.isDisplayable()) return;
                    if (action == 0) clear();
                    else if (action == 1) { cancelled = true; signingDialog.dispose(); }
                    else if (points() >= 3) { accepted = true; signingDialog.dispose(); }
                    else JOptionPane.showMessageDialog(signingDialog, "Please sign before accepting.");
                });
            }
            if (!down) buttonDown = false;
            current = null;
            return;
        }
        if (!down) { current = null; return; }
        if (current == null) { current = new ArrayList<>(); strokes.add(current); }
        current.add(new Point2D.Double(Math.max(0, Math.min(W - 1, data.getX() * (W - 1.0) / maxX)),
                                      Math.max(0, Math.min(H - 1, data.getY() * (H - 1.0) / maxY))));
        if (canvas != null) SwingUtilities.invokeLater(canvas::repaint);
    }
    private synchronized void clear() {
        strokes.clear(); current = null;
        if (canvas != null) canvas.repaint();
        try { if (deviceControls) drawDeviceControls(); else tablet.setClearScreen(); } catch (Exception ignored) { }
    }
    private synchronized int points() {
        int n = 0; for (var stroke : strokes) n += stroke.size(); return n;
    }
    private synchronized void render(Graphics2D g) {
        g.setColor(new Color(18, 58, 117));
        g.setStroke(new BasicStroke(3.2f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
        for (var stroke : strokes) {
            if (stroke.isEmpty()) continue;
            Path2D path = new Path2D.Double();
            path.moveTo(stroke.get(0).x, stroke.get(0).y);
            for (int i = 1; i < stroke.size(); i++) path.lineTo(stroke.get(i).x, stroke.get(i).y);
            if (stroke.size() == 1) g.fill(new Ellipse2D.Double(stroke.get(0).x, stroke.get(0).y, 3, 3));
            else g.draw(path);
        }
    }
    private void drawDeviceControls() throws Exception {
        BufferedImage img = new BufferedImage(screenWidth, screenHeight, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        try {
            g.setColor(Color.WHITE); g.fillRect(0, 0, screenWidth, screenHeight);
            g.setColor(new Color(16, 51, 82));
            g.fillRect(0, 0, screenWidth, Math.max(32, screenHeight / 10));
            g.setColor(Color.WHITE);
            g.setFont(new Font("SansSerif", Font.BOLD, Math.max(14, screenHeight / 20)));
            g.drawString("ITHUTESIGN  -  Sign below", 16, Math.max(23, screenHeight / 15));
            int top = (int)(screenHeight * 0.83);
            String[] labels = {"CLEAR", "CANCEL", "ACCEPT"};
            Color[] colors = {new Color(16, 51, 82), new Color(115, 49, 49), new Color(24, 125, 78)};
            for (int i = 0; i < 3; i++) {
                int x = i * screenWidth / 3;
                int right = (i + 1) * screenWidth / 3;
                g.setColor(colors[i]); g.fillRect(x + 2, top, right - x - 4, screenHeight - top);
                g.setColor(Color.WHITE);
                g.setFont(new Font("SansSerif", Font.BOLD, Math.max(13, screenHeight / 18)));
                FontMetrics fm = g.getFontMetrics();
                g.drawString(labels[i], x + (right - x - fm.stringWidth(labels[i])) / 2,
                    top + (screenHeight - top + fm.getAscent()) / 2 - 3);
            }
        } finally { g.dispose(); }
        byte[] pixels = new byte[screenWidth * screenHeight * 3];
        int at = 0;
        for (int y = 0; y < screenHeight; y++) for (int x = 0; x < screenWidth; x++) {
            int rgb = img.getRGB(x, y);
            pixels[at++] = (byte)(rgb >>> 16);
            pixels[at++] = (byte)(rgb >>> 8);
            pixels[at++] = (byte)rgb;
        }
        tablet.setInkingMode(InkingMode.Off);
        tablet.writeImage(EncodingMode.EncodingMode_24bit, pixels);
        tablet.setInkingMode(InkingMode.On);
    }
    private void capture(Path output) throws Exception {
        UsbDevice device = find();
        if (device == null) throw new IllegalStateException("STU-540 not detected");
        tablet = new Tablet();
        try {
            int status = tablet.usbConnect(device, true);
            if (status != 0 || !tablet.isConnected()) throw new IllegalStateException("Tablet connection failed: " + status);
            Capability cap = tablet.getCapability();
            maxX = cap.getTabletMaxX(); maxY = cap.getTabletMaxY();
            screenWidth = cap.getScreenWidth(); screenHeight = cap.getScreenHeight();
            if (maxX <= 0 || maxY <= 0) throw new IllegalStateException("Invalid tablet dimensions");
            ITabletHandler handler = (ITabletHandler) Proxy.newProxyInstance(
                ITabletHandler.class.getClassLoader(), new Class<?>[]{ITabletHandler.class},
                (proxy, method, args) -> {
                    if (args != null && args.length == 1 && args[0] instanceof PenData &&
                        (method.getName().equals("onPenData") || method.getName().equals("onPenDataOption") ||
                         method.getName().equals("onPenDataTimeCountSequence"))) pen((PenData)args[0]);
                    return null;
                });
            tablet.addTabletHandler(handler);
            if (deviceControls) {
                if (screenWidth <= 0 || screenHeight <= 0 || screenWidth > 4096 || screenHeight > 4096)
                    throw new IllegalStateException("Invalid STU display dimensions");
                drawDeviceControls();
            } else {
                tablet.setClearScreen();
                tablet.setInkingMode(InkingMode.On);
            }
            SwingUtilities.invokeAndWait(() -> {
                JDialog dialog = new JDialog((Frame)null, "IthuteSign | STU-540 signature", true);
                dialog.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
                signingDialog = dialog;
                canvas = new JPanel() {
                    protected void paintComponent(Graphics g) {
                        super.paintComponent(g);
                        Graphics2D g2 = (Graphics2D)g.create();
                        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                        synchronized (STUCapture.this) { render(g2); }
                        g2.dispose();
                    }
                };
                canvas.setPreferredSize(new Dimension(W, H));
                canvas.setBackground(Color.WHITE);
                JButton clearButton = new JButton("Clear");
                clearButton.addActionListener(e -> clear());
                JButton cancelButton = new JButton("Cancel");
                cancelButton.addActionListener(e -> { cancelled = true; dialog.dispose(); });
                JButton acceptButton = new JButton("Accept signature");
                acceptButton.addActionListener(e -> {
                    if (points() < 3) {
                        JOptionPane.showMessageDialog(dialog, "Please sign on the STU-540 first.");
                        return;
                    }
                    accepted = true; dialog.dispose();
                });
                Color navy = new Color(16, 51, 82);
                Color green = new Color(24, 125, 78);
                JPanel header = new JPanel(new BorderLayout(8, 6));
                header.setBackground(navy);
                header.setBorder(BorderFactory.createEmptyBorder(14, 18, 14, 18));
                JLabel brand = new JLabel("ITHUTESIGN  |  Secure Document Signing");
                brand.setFont(new Font("SansSerif", Font.BOLD, 20));
                brand.setForeground(Color.WHITE);
                JLabel instructions = new JLabel("Sign on the Wacom STU-540. Review your signature before accepting.");
                instructions.setFont(new Font("SansSerif", Font.PLAIN, 13));
                instructions.setForeground(new Color(225, 239, 246));
                header.add(brand, BorderLayout.NORTH);
                header.add(instructions, BorderLayout.SOUTH);
                canvas.setBorder(BorderFactory.createLineBorder(new Color(204, 220, 231), 2));
                JPanel actions = new JPanel(new FlowLayout(FlowLayout.RIGHT, 12, 12));
                actions.setBackground(new Color(238, 246, 250));
                clearButton.setToolTipText("Erase the current signature and start again");
                cancelButton.setToolTipText("Close without saving a signature");
                acceptButton.setToolTipText("Save the captured signature");
                acceptButton.setBackground(green);
                acceptButton.setForeground(Color.WHITE);
                acceptButton.setFont(new Font("SansSerif", Font.BOLD, 14));
                acceptButton.setOpaque(true);
                clearButton.setFocusable(false);
                cancelButton.setFocusable(false);
                acceptButton.setFocusable(false);
                actions.add(clearButton); actions.add(cancelButton); actions.add(acceptButton);
                dialog.getRootPane().setDefaultButton(acceptButton);
                dialog.getRootPane().registerKeyboardAction(e -> { cancelled = true; dialog.dispose(); },
                    KeyStroke.getKeyStroke(KeyEvent.VK_ESCAPE, 0),
                    JComponent.WHEN_IN_FOCUSED_WINDOW);
                dialog.add(header, BorderLayout.NORTH);
                dialog.add(canvas, BorderLayout.CENTER);
                dialog.add(actions, BorderLayout.SOUTH);
                dialog.pack(); dialog.setLocationRelativeTo(null);
                dialog.addWindowListener(new WindowAdapter() {
                    public void windowClosing(WindowEvent e) { cancelled = true; }
                });
                dialog.setVisible(true);
                signingDialog = null;
            });
            if (!accepted || cancelled) throw new IllegalStateException("Signature capture cancelled");
            // Export only the actual ink, not the tablet's full 800x480 canvas.
            // Preserve stroke aspect ratio and a small transparent safety margin.
            double minX = W, minY = H, maxX = 0, maxY = 0;
            synchronized (this) {
                for (var stroke : strokes) for (var point : stroke) {
                    minX = Math.min(minX, point.x); minY = Math.min(minY, point.y);
                    maxX = Math.max(maxX, point.x); maxY = Math.max(maxY, point.y);
                }
            }
            if (points() < 3) throw new IllegalStateException("Signature contains insufficient ink");
            int padding = 12;
            int left = Math.max(0, (int)Math.floor(minX) - padding);
            int top = Math.max(0, (int)Math.floor(minY) - padding);
            int right = Math.min(W, (int)Math.ceil(maxX) + padding + 1);
            int bottom = Math.min(H, (int)Math.ceil(maxY) + padding + 1);
            BufferedImage img = new BufferedImage(right - left, bottom - top, BufferedImage.TYPE_INT_ARGB);
            Graphics2D g = img.createGraphics();
            g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g.translate(-left, -top);
            synchronized (this) { render(g); }
            g.dispose();
            Path parent = output.toAbsolutePath().getParent();
            if (parent == null || !Files.isDirectory(parent)) throw new IllegalArgumentException("Output directory unavailable");
            Path temporary = Files.createTempFile(parent, ".ithutesign-", ".png");
            try {
                if (!ImageIO.write(img, "PNG", temporary.toFile())) throw new IllegalStateException("PNG encoder unavailable");
                Files.move(temporary, output, StandardCopyOption.ATOMIC_MOVE);
            } finally { Files.deleteIfExists(temporary); }
        } finally {
            if (tablet != null) {
                try { tablet.setInkingMode(InkingMode.Off); } catch (Exception ignored) {}
                try { tablet.setClearScreen(); } catch (Exception ignored) {}
                tablet.disconnect();
            }
        }
    }
    /** Draw a temporary on-screen message. Never changes ROM or boot image. */
    private static void displayMessage(boolean thanks) throws Exception {
        UsbDevice device = find();
        if (device == null) throw new IllegalStateException("STU-540 not detected");
        Tablet screen = new Tablet();
        try {
            int status = screen.usbConnect(device, true);
            if (status != 0 || !screen.isConnected())
                throw new IllegalStateException("Tablet connection failed: " + status);
            Capability cap = screen.getCapability();
            int width = cap.getScreenWidth();
            int height = cap.getScreenHeight();
            if (width <= 0 || height <= 0 || width > 4096 || height > 4096)
                throw new IllegalStateException("Invalid STU screen dimensions");
            BufferedImage picture = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
            Graphics2D g = picture.createGraphics();
            try {
                g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                g.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
                g.setColor(Color.WHITE);
                g.fillRect(0, 0, width, height);
                // Scale a single vector design to the actual STU display dimensions.
                double scale = Math.min(width / 800.0, height / 480.0);
                g.translate((width - 800 * scale) / 2.0, (height - 480 * scale) / 2.0);
                g.scale(scale, scale);
                Color navy = new Color(16, 51, 82);
                Color green = new Color(24, 125, 78);
                g.setColor(new Color(238, 246, 250));
                g.fillRoundRect(24, 18, 752, 444, 24, 24);
                g.setColor(navy);
                g.setStroke(new BasicStroke(5f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                // Document-and-pen emblem; no external assets or image decoder required.
                g.drawRoundRect(352, 42, 96, 116, 12, 12);
                g.drawLine(370, 74, 415, 74);
                g.drawLine(370, 91, 415, 91);
                g.drawLine(370, 108, 402, 108);
                g.setColor(green);
                g.setStroke(new BasicStroke(8f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                g.drawLine(444, 51, 414, 132);
                g.setStroke(new BasicStroke(4f, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
                g.drawArc(368, 115, 58, 27, 5, 155);
                g.setColor(navy);
                g.setFont(new Font("SansSerif", Font.BOLD, 44));
                FontMetrics metrics = g.getFontMetrics();
                String title = "ITHUTESIGN";
                g.drawString(title, (800 - metrics.stringWidth(title)) / 2, 222);
                g.setFont(new Font("SansSerif", Font.PLAIN, 22));
                String subtitle = thanks ? "Thank you for signing" : "Secure Document Signing";
                metrics = g.getFontMetrics();
                g.drawString(subtitle, (800 - metrics.stringWidth(subtitle)) / 2, 266);
                g.setColor(new Color(220, 239, 226));
                g.fillRoundRect(226, 309, 348, 78, 20, 20);
                g.setColor(green);
                g.setFont(new Font("SansSerif", Font.BOLD, 27));
                String statusText = thanks ? "Signature Captured" : "Ready to Sign";
                metrics = g.getFontMetrics();
                g.drawString(statusText, (800 - metrics.stringWidth(statusText)) / 2, 359);
            } finally {
                g.dispose();
            }
            // Wacom 24-bit mode takes packed RGB pixel data, not PNG bytes.
            byte[] pixels = new byte[width * height * 3];
            int at = 0;
            for (int y = 0; y < height; y++) {
                for (int x = 0; x < width; x++) {
                    int rgb = picture.getRGB(x, y);
                    pixels[at++] = (byte)((rgb >>> 16) & 255);
                    pixels[at++] = (byte)((rgb >>> 8) & 255);
                    pixels[at++] = (byte)(rgb & 255);
                }
            }
            screen.setInkingMode(InkingMode.Off);
            screen.writeImage(EncodingMode.EncodingMode_24bit, pixels);
            System.out.println("STU-540 display image sent");
        } finally {
            try { screen.disconnect(); } catch (Exception ignored) {}
        }
    }
    private static UsbDevice find() {
        for (UsbDevice d : UsbDevice.getUsbDevices())
            if ((d.getIdVendor() & 0xffff) == 0x056a && (d.getIdProduct() & 0xffff) == 0x00a8) return d;
        return null;
    }
    public static void main(String[] args) {
        try {
            if (args.length == 1 && args[0].equals("--probe")) {
                if (find() == null) { System.err.println("STU-540 not detected"); System.exit(10); }
                System.out.println("STU-540 detected"); return;
            }
            if (args.length == 1 && (args[0].equals("--welcome") || args[0].equals("--thanks"))) {
                displayMessage(args[0].equals("--thanks")); return;
            }
            if (args.length == 2 && args[0].equals("--device-controls")) {
                STUCapture capture = new STUCapture();
                capture.deviceControls = true;
                capture.capture(Path.of(args[1]));
                return;
            }
            if (args.length != 1 || args[0].startsWith("--")) { System.err.println("Usage: STUCapture --probe | --welcome | --thanks | [--device-controls] output.png"); System.exit(12); }
            new STUCapture().capture(Path.of(args[0]));
        } catch (UnsatisfiedLinkError e) { System.err.println("Wacom native library unavailable: " + e); System.exit(11);
        } catch (Exception e) { System.err.println(e.getMessage()); System.exit(13); }
    }
}
