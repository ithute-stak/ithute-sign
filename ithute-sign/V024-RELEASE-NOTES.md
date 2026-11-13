# IthuteSign v0.24 — Offline source release candidate

Additional hardening:
- The capture dialog refuses to proceed without an acceptable signature.
- The app validates the exported signature image before adding it to the PDF queue.
- The release build deletes stale installer and release-mode artifacts before compiling.
- Development builds no longer silently generate installer packages.
- Inno Setup 7 detection includes per-user installation locations.

Acceptance still required on Windows:
1. Build-release.bat completes, and preflight-release.ps1 succeeds.
2. STU-540 captures live handwriting and Clear removes it on both screens.
3. Cancel and failed recapture do not reuse previous ink.
4. Drag and resize signatures, then inspect a newly signed two-page PDF.
5. Open a DOCX in locally installed Microsoft Word and verify PDF export.
6. Confirm source document remains unchanged and audit JSON is generated.

This is a complete source distribution, not a compiled installer. Handwriting is
embedded as an electronic image, not a cryptographic PDF digital signature.
