# IthuteSign WinUI 3 dashboard (v0.30 handoff)

Modern C# / WinUI 3 frontend, currently implemented as a companion launcher for the existing tested Python signing application. Choose PDF/DOC/DOCX and click Launch signing app. The selected file is passed to the classic application as `--open <path>`, requiring the bundled updated classic signer.

Requirements: Windows 10 19041+ or Windows 11, .NET 8 SDK, Windows App SDK WinUI 3 development environment. Run `build-modern.bat`. This source has not yet been compiled on Windows in this release.

The classic executable path is resolved in `IthuteSign.Modern/MainWindow.xaml.cs`; edit the candidate list if testing from a different folder. Recent documents are session-only, never uploaded. Do not remove your working v0.28 installation.
