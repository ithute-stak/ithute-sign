# IthuteSign v0.23 — Offline release candidate

- Retains verified Wacom STU-540 live handwriting capture and dual-screen clear.
- Retains PDF/Word-to-PDF workflow, signature dragging, resizing, and save confirmation.
- Prevents stale signature reuse if a new tablet capture fails or is cancelled.
- Adds regression tests for two-page signature embedding, audit creation, and source/output preservation.
- Supports Inno Setup 6/7 via build-windows.bat.

Build on Windows with `build-release.bat`. This archive is source only, not a compiled Windows installer.
The new changes require real Windows hardware and installed-app acceptance tests.
