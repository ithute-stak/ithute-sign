@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Strict build: unit tests, STU bridge, packaged executable and Inno installer.
call "%~dp0build-windows.bat" --release
if errorlevel 1 (
  echo ERROR: IthuteSign release build failed.
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0preflight-release.ps1"
if errorlevel 1 (
  echo ERROR: IthuteSign release preflight failed.
  exit /b 1
)
echo SUCCESS: IthuteSign release installer passed file checks.
echo NOTE: Test the installed app with the physical STU-540 before use.
exit /b 0
