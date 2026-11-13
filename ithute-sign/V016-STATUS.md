# IthuteSign v0.16 — source package status

This archive includes the Windows desktop app, Wacom C# bridge, detect/reconnect controls, pen counters, and the new 10-second no-pen-report warning.

## Confirmed on user Windows 10 machine (earlier revision)
- MSBuild compiles bridge
- Wacom STU-540 USB probe returns 0
- Tablet displays handwriting
- PC bridge receives zero onPenData events; capture remains blocked

## Not yet verified
- Compilation of this v0.16 revision on Windows
- Actual STU-540 pen data callback or alternative capture mechanism
- End-to-end signature saving, PDF/Word workflow and installer acceptance

## Test
1. Close STUCapture.exe.
2. Extract contents to C:\ithute-sign (avoid nested duplicate directory).
3. Run build-bridge.bat from Command Prompt.
4. Run wacom-bridge\bin\STUCapture.exe --probe then echo %ERRORLEVEL% on a separate line.
5. Run wacom-bridge\bin\STUCapture.exe "%TEMP%\ithute-sign-v016.png" and check counters and watchdog.

No Wacom proprietary DLL is distributed. The official SDK must be installed locally.
