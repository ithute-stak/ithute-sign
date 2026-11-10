# Import status — IthuteSign v0.12

This repository is being populated from the locally tested IthuteSign-Windows-Source-v0.12.zip archive (30 entries).

## Current GitHub branch
- `import-ithutesign-v0.12`, draft PR #1.
- Basic device probing and signature placement geometry modules.
- Windows source checks and unit tests.

## Not yet imported
- Complete document processing and PySide6 desktop UI
- C# Wacom signature capture and branded tablet display implementation
- Windows build scripts, Inno Setup manifest, and remaining tests

**The PR MUST remain draft and MUST NOT be merged into main before all required files are imported and source CI succeeds.**

## External dependencies
The official Wacom STU driver and SDK must be obtained and installed separately on Windows. Do not commit vendor binaries, certificates, or private documents. This application has no activation, login, or subscription requirement.

## Acceptance
A Windows runner can compile and exercise the Python source but cannot establish that an STU-540 is physically connected. Final production acceptance requires on-device tests for Welcome, Capture, Clear/OK/Cancel, Thank You, and PDF export.
