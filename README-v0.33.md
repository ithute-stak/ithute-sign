# IthuteSign v0.33 — WinUI document workspace hardening

This source increment adds local file metadata to the WinUI workspace and prevents PDF preview pop-up windows and downloads in WebView2, in addition to the existing navigation restrictions. The verified v0.28 Python/C# signing workflow is unchanged.

## Build and acceptance

1. Extract to a NEW folder (do not overwrite the working v0.28 installation).
2. Install the .NET 8 SDK and Windows App SDK prerequisites.
3. Run `ithutesign-winui-v029\build-modern.bat` from Command Prompt.
4. Open a PDF and verify file details and preview; open a PDF with a hyperlink and verify it cannot open a new window; verify the Launch signing app handoff still works.
5. Open a DOCX and verify the existing signing application opens it.

## Important limits

WinUI has not been compiled or hardware-tested here. The PDF preview is read-only. Signature placement, capture, and saving still occur in the verified PySide6 application, launched separately. This is not a complete WinUI replacement, and it is not 10/10 ready.
