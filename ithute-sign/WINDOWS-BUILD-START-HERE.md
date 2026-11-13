# IthuteSign Windows source package

This package includes the Python desktop app, Wacom C# bridge, Windows build scripts, tests, and installer source.

## Build and test on Windows

1. Extract the contents of the `ithute-sign` directory to `C:\ithute-sign`.
2. Install the official Wacom STU SDK and .NET Framework 4.8 Developer Pack; use modern Visual Studio MSBuild.
3. Close all running STUCapture.exe instances.
4. Open Command Prompt and run:

    cd /d C:\ithute-sign
    build-bridge.bat
    wacom-bridge\bin\STUCapture.exe --probe
    echo %ERRORLEVEL%

5. Start signature capture:

    wacom-bridge\bin\STUCapture.exe "%TEMP%\ithute-sign-diagnostic.png"

Use Detect tablet and Connect / Reconnect. Check the pen event and contact counters.

**Important:** USB detection has passed on the user's STU-540, but zero pen events were received in the earlier build. This update adds connection controls and diagnostics; it is **not yet a confirmed pen-data fix**. Do not deploy for production signatures until hardware capture, PDF export, and Windows installer acceptance tests pass.

The official Wacom SDK DLL is not redistributed in this source ZIP.
