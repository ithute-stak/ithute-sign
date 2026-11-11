# IthuteSign import and hardware acceptance status

Repository: `ithute-stak/ithute-sign`
Integration branch: `import-ithutesign-v0.12`
PR: #1 (DRAFT — do not merge/release yet)

## Imported source
- `app/main.py`: PySide6 desktop signing workspace and PDF page preview
- `app/document.py`: PDF/DOC/DOCX intake (DOC/DOCX conversion via Microsoft Word on Windows), visual signature placement, signed-PDF export and SHA-256 audit sidecar
- `app/device.py`: bridge probe and welcome/thanks commands
- `app/geometry.py`: placement geometry
- `tests/`: source, geometry, document and device unit tests
- Windows build scripts and Inno Setup manifest
- GitHub Actions source checks and strict release completeness gate

## Known blockers (explicit)
- `wacom-bridge/STUCapture.cs` is **not yet present**. The project file alone does not implement USB discovery, tablet display, handwriting capture or PNG export.
- Vendor SDK interop DLL must be installed locally from the official Wacom SDK; do not commit vendor binaries.
- Windows packaging has not been proven by a successful Windows installer artifact.
- STU-540 Welcome, Capture, Clear/OK/Cancel and Thank You must be tested on physical hardware.
- PDF signatures currently are embedded signature-image appearances, **not cryptographic PDF digital signatures**. Audit JSON records hashes but is not a certificate/trust validation mechanism.

## Latest automated status
- Windows source-check workflow: success on commit `b8b132ffd952af029e623ccb3c6eaabee86101f6`.
- This is source CI only; it is not evidence of a compiled installer or physical device acceptance.

## Release gate
Keep PR #1 draft. Do not tag, merge as release-ready, or describe error 127 as fixed until:
1. The actual C# bridge source is imported and builds against the official SDK.
2. A Windows build produces a distributable installer artifact.
3. On a real STU-540, verify USB probe, Ithute welcome display, handwritten capture, clear/cancel/confirm, thanks screen and signed-PDF output.
4. Verify original document remains unchanged and exported PDF opens.
5. Clearly label image-based signature output as an electronic signature appearance, not a certificate-based digital signature.

## Product constraints
IthuteSign is designed to run locally without online activation, login, subscription or license server. Respect vendor license terms for Wacom SDK/driver.
