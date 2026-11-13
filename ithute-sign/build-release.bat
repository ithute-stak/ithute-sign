@echo off
setlocal EnableExtensions
cd /d "%~dp0"
REM Strict build: unit tests, STU bridge, packaged executable and Inno installer.
REM Remove stale release artifacts so old installers cannot be mistaken for a new build.
if exist "dist\installer\IthuteSign-Setup.exe" del /F /Q "dist\installer\IthuteSign-Setup.exe" || exit /b 1
if exist "dist\IthuteSign\release-mode.flag" del /F /Q "dist\IthuteSign\release-mode.flag" || exit /b 1
call "%~dp0build-bridge.bat"
if errorlevel 1 (
  echo ERROR: Wacom bridge build failed.
  exit /b 1
)
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
