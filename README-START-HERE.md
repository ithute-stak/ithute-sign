# IthuteSign v0.30 — WinUI 3 + tested signing engine handoff

This source package includes TWO separate applications:

* `ithute-sign/`: classic Python/PySide6 signer + C# Wacom STU-540 bridge, based on v0.28 with one new command-line entry point (`--open <document>`). It is not a replacement for your currently installed v0.28 until you test it.
* `ithutesign-winui-v029/`: WinUI 3 desktop dashboard, now capable of opening the selected document in the classic signer. The document path is passed as an argument array (not shell-interpolated).

## Windows build order

1. Extract this ZIP into a **new** folder, e.g. `C:\ithute-sign-v030-test`. Do not overwrite the tested v0.28 source or installer.
2. Build classic signer from `ithute-sign\` with `build-windows.bat`. This requires the existing configured Wacom SDK and Windows build dependencies.
3. Build modern dashboard from `ithutesign-winui-v029\` with `build-modern.bat`. This requires the .NET 8 SDK and Windows App SDK / WinUI development tooling. **This WinUI build has not been tested in the Linux packaging environment.**
4. The modern dashboard currently searches for classic signer at `%ProgramFiles%\IthuteSign\IthuteSign.exe` or `C:\ithute-sign\dist\IthuteSign\IthuteSign.exe`. To test the updated `--open` handoff, point it at your newly built classic signer (or install the updated classic build only after a backup and acceptance test). The already-installed v0.28 may not recognize `--open`.
5. Open a PDF or DOCX in the modern dashboard, click **Launch signing app**, verify it appears in the classic signer, capture on STU-540, drag/resize, save and reopen the signed PDF. Also test paths with spaces and non-ASCII names.

## Test results and limits

* 26 Python regression tests passed in the packaging environment.
* Source ZIP integrity verified.
* **No Windows WinUI compilation, device testing or installer testing was performed for v0.30.**
* This is a transitional two-process architecture, not yet a fully native WinUI signing workspace. Keep the v0.28 installed application as the production fallback.
* The saved signature is an embedded handwritten image, not a certificate-backed PDF digital signature.
