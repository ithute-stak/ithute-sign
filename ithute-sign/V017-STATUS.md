# IthuteSign v0.17 — Windows source distribution

Includes all v0.16 source modules plus a raw callback heartbeat with a last-received timestamp.

## Hardware validation still required
- C# bridge must be rebuilt on Windows with installed Wacom SDK.
- USB probe previously passed on the user's STU-540.
- The current COM pen callback has returned zero events during real signing.
- This release does **not** implement or validate native polling fallback.
- Do not treat the signature workflow as production-ready.

## Windows commands
Close any running STUCapture.exe before rebuilding.
`cd /d C:\ithute-sign`
`build-bridge.bat`
`wacom-bridge\bin\STUCapture.exe "%TEMP%\ithute-sign-v017.png"`

Report the Raw callbacks counter and Last callback timestamp after signing.
