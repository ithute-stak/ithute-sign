# IthuteSign v0.31 — Offline WinUI dashboard improvements

Includes all v0.30 sources. Changes are isolated to `ithutesign-winui-v029/IthuteSign.Modern` and do not modify the tested Python/Wacom signing engine.

## Added
- Recent document paths saved locally at `%LOCALAPPDATA%\IthuteSign\modern-settings.json` (no network use). Missing paths filtered on startup.
- Optional configurable absolute path to the installed signing engine, with file existence validation.
- Clear recent documents button.
- Atomic settings replacement via temp file and `File.Move(..., true)`.

## Build
Extract to a NEW directory. In the `ithutesign-winui-v029` folder run `build-modern.bat` on Windows with .NET 8 SDK. Do not overwrite the verified v0.28 application.

## Not yet done
Native WinUI PDF canvas, in-process Wacom capture, and Windows compilation/acceptance testing of this new dashboard. The dashboard continues to launch the tested signing application.
