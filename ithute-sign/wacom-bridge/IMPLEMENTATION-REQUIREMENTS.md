# Wacom STU-540 bridge implementation requirements

This file defines the real bridge contract. A stub or simulated capture must never return success.

## Build
- Windows x86/.NET Framework 4.8, matching the STU-540 SDK interop architecture.
- Reference official vendor `Interop.wgssSTU.dll` from the locally installed SDK (do not commit vendor DLLs).
- Build to `wacom-bridge/bin/STUCapture.exe`; bundle required redistributable interop/runtime files beside it.

## CLI contract consumed by app/device.py
- `STUCapture.exe --probe`: enumerate STU devices via SDK; exit 0 only if a real device opens; exit 10 if none; 11 SDK/driver failure; 13 unexpected SDK exception.
- `STUCapture.exe --welcome`: open device, render IthuteSign-branded welcome screen to tablet, return nonzero on any SDK/display failure.
- `STUCapture.exe --thanks`: render thank-you screen, nonzero on failure.
- `STUCapture.exe <output.png>`: show signing UI on tablet, collect pen packets/pressure until confirmed, honor clear/cancel; create transparent PNG only after confirm, exit nonzero on cancel/error. Output must be valid PNG and never a fake/blank success.
- Send human-readable diagnostics to stdout/stderr; no success exit code on device/SDK errors.

## Hardware acceptance checklist
1. Probe detects a physically attached STU-540 and fails when unplugged.
2. Welcome and thanks screens render legibly with Ithute logo.
3. Capture receives pen-down/move/up events and preserves pressure/strokes.
4. Clear removes all strokes; Cancel produces no output; OK produces valid transparent PNG.
5. Desktop preview matches tablet handwriting.
6. Disconnect/reconnect is handled without crashing.
7. End-to-end PDF export opens and source file hash remains unchanged.

**Status:** Specification only. Native C# implementation and physical validation remain outstanding.
