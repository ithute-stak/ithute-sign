# IthuteSign v0.21 release preparation

- Fixed missing `preflight-release.ps1` referenced by `build-release.bat`.
- Release script builds the Wacom bridge before packaging.
- Installer version aligned to 0.21.0.
- Release preflight checks Windows EXE, Wacom bridge, interop DLL, release-mode marker, and installer output.
- Production mode does not allow mouse-only signatures.

## Build on Windows
Close the Wacom bridge, then run `build-release.bat` with Python, Wacom SDK, Visual Studio and Inno Setup 6 installed.

## Not yet verified
End-to-end Accept Signature PNG saving, PDF/Word output, installer build and post-install hardware testing.
