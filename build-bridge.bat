@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-wacom.ps1" -SkipInstall %*
if errorlevel 1 exit /b %errorlevel%
if exist "wacom-bridge\branding\ithute-logo.png" (
  if not exist "wacom-bridge\bin\branding" mkdir "wacom-bridge\bin\branding"
  copy /Y "wacom-bridge\branding\ithute-logo.png" "wacom-bridge\bin\branding\" || exit /b 1
)
exit /b 0
