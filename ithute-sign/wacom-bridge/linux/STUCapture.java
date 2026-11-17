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

    private synchronized void pen(PenData data) {
        if (cancelled || accepted) return;
        boolean down = data.getSw() != 0 && data.getPressure() > 0;
        if (!down) { current = null; return; }
        if (current == null) { current = new ArrayList<>(); strokes.add(current); }
        current.add(new Point2D.Double(Math.max(0, Math.min(W - 1, data.getX() * (W - 1.0) / maxX)),
                                      Math.max(0, Math.min(H - 1, data.getY() * (H - 1.0) / maxY))));
        if (canvas != null) SwingUtilities.invokeLater(canvas::repaint);
    }
    private synchronized void clear() {
        strokes.clear(); current = null;
        if (canvas != null) canvas.repaint();
        try { tablet.setClearScreen(); } catch (Exception ignored) { }
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
    private void capture(Path output) throws Exception {
        UsbDevice device = find();
        if (device == null) throw new IllegalStateException("STU-540 not detected");
        tablet = new Tablet();
        try {
            int status = tablet.usbConnect(device, true);
            if (status != 0 || !tablet.isConnected()) throw new IllegalStateException("Tablet connection failed: " + status);
            Capability cap = tablet.getCapability();
            maxX = cap.getTabletMaxX(); maxY = cap.getTabletMaxY();
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
            tablet.setClearScreen();
            tablet.setInkingMode(InkingMode.On);
            SwingUtilities.invokeAndWait(() -> {
                JDialog dialog = new JDialog((Frame)null, "IthuteSign | STU-540 signature", true);
                dialog.setDefaultCloseOperation(WindowConstants.DISPOSE_ON_CLOSE);
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
                JPanel actions = new JPanel();
                actions.add(clearButton); actions.add(cancelButton); actions.add(acceptButton);
                dialog.add(new JLabel("Sign on the Wacom STU-540, then accept below."), BorderLayout.NORTH);
                dialog.add(canvas, BorderLayout.CENTER);
                dialog.add(actions, BorderLayout.SOUTH);
                dialog.pack(); dialog.setLocationRelativeTo(null);
                dialog.addWindowListener(new WindowAdapter() {
                    public void windowClosing(WindowEvent e) { cancelled = true; }
                });
                dialog.setVisible(true);
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
                g.setColor(Color.WHITE);
                g.fillRect(0, 0, width, height);
                g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
                g.setColor(new Color(16, 51, 82));
                g.setFont(new Font("SansSerif", Font.BOLD, Math.max(22, width / 19)));
                String title = "ITHUTESIGN";
                FontMetrics metrics = g.getFontMetrics();
                g.drawString(title, (width - metrics.stringWidth(title)) / 2, height / 3);
                g.setFont(new Font("SansSerif", Font.PLAIN, Math.max(15, width / 33)));
                String line = thanks ? "Thank you for signing" : "Secure Document Signing";
                metrics = g.getFontMetrics();
                g.drawString(line, (width - metrics.stringWidth(line)) / 2, height / 2);
                String instruction = thanks ? "Signature captured" : "Ready to Sign";
                g.setFont(new Font("SansSerif", Font.BOLD, Math.max(16, width / 30)));
                metrics = g.getFontMetrics();
                g.drawString(instruction, (width - metrics.stringWidth(instruction)) / 2,
                             height * 2 / 3);
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
            if (args.length != 1 || args[0].startsWith("--")) { System.err.println("Usage: STUCapture --probe | output.png"); System.exit(12); }
            new STUCapture().capture(Path.of(args[0]));
        } catch (UnsatisfiedLinkError e) { System.err.println("Wacom native library unavailable: " + e); System.exit(11);
        } catch (Exception e) { System.err.println(e.getMessage()); System.exit(13); }
    }
}
