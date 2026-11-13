# IthuteSign v0.26 — Release candidate

- Detects source document changes between opening and saving. Refuses to sign if the source file changed or disappeared.
- Windows release preflight checks installer freshness and prints SHA-256 digest.
- Adds two regression tests for source-change protection and release preflight.
- Retains working STU-540 bridge code, dual-screen Clear, PDF placement and resizing, and DOC/DOCX conversion.

Automated tests run in Linux; Windows packaging and physical tablet acceptance are still required.
This is source code, not a Windows executable.
