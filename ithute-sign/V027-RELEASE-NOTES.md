# IthuteSign v0.27 — Offline source release candidate

- Ensures Microsoft Word COM cleanup and Python COM uninitialization even when closing a document raises an exception.
- Adds four negative-path PDF signing tests: out-of-bounds placement, missing signature image, source overwrite rejection, existing audit protection.
- Preserves Wacom STU-540 pen-mode workaround, dual-screen Clear, drag, resize, capture validation and release build safeguards.
- The full source ZIP is verified and Python tests pass. Windows GUI interaction, Word conversion, Wacom hardware, and installer compilation have not been tested in this environment.

## Build
Extract into C:\\ithute-sign, then run build-release.bat on Windows with Wacom SDK, Python, Visual Studio Build Tools, and Inno Setup installed.

The output embeds handwritten electronic signature images; it is not a certificate-based cryptographic PDF signature.
