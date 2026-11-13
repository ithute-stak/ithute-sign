# IthuteSign v0.32 — native WinUI PDF preview milestone

The WinUI 3 dashboard now embeds a **read-only local PDF preview** via WinUI WebView2. It uses the selected local PDF path; it does not upload documents. Navigation away from that selected file is blocked in the preview. DOC/DOCX preview is not supported; the existing Python signer handles Word conversion.

## Limits

This is **not yet native signature positioning**. The existing PySide6 application remains responsible for signature capture, placement, resizing, saving, and audit evidence. Do not replace the verified v0.28 production installation. WinUI compilation and real Windows acceptance are pending.

## Build

Extract into a fresh folder. Build `ithutesign-winui-v029/build-modern.bat` on Windows with .NET 8 SDK and Windows App SDK prerequisites. Run the dashboard, choose a PDF, click Preview selected PDF, then Launch signing app. Verify PDF preview, blocked external navigation, and DOCX handoff. Preserve the existing v0.28 installation as fallback.
