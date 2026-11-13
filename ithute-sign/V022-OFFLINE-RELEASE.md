# IthuteSign v0.22 — Complete offline source bundle

This ZIP is the complete buildable source distribution, not a precompiled installer.

Includes:
- Offline PDF document viewer and Wacom STU-540 capture bridge
- DOC/DOCX conversion to PDF using locally installed Microsoft Word
- Handwritten PNG signatures, multiple signatures per document, and audit JSON
- Drag-to-move and select-to-resize existing signature placements
- Save confirmation, original-document preservation, and page-boundary checks
- Dual-screen Wacom Clear action and basic pen report mode fix
- Windows MSBuild, PyInstaller, Inno Setup 6/7 scripts and release preflight

## Windows build
Extract into C:\\ithute-sign. Close the running application.
Run `build-release.bat` in Command Prompt.
The Windows compiler, Wacom SDK, Python, Microsoft Word (for DOC/DOCX), and Inno Setup 6 or 7 must be installed locally.

## Verification status
Python source tests run in this environment. Windows C# compilation, installer build and drag/resize acceptance require testing on your Windows machine.
PDF signing has previously been verified with an actual output PDF.
This uses visual handwritten electronic signatures, NOT certificate-backed cryptographic signatures.
