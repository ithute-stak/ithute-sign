@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>&1 || (echo Python launcher not found & exit /b 1)
py -3 -m venv .venv || exit /b 1
call .venv\Scripts\activate.bat || exit /b 1
python -m pip install --upgrade pip || exit /b 1
pip install -r requirements.txt || exit /b 1
python -m unittest discover -s tests -v || exit /b 1
REM Place the C# bridge executable and SDK-compatible interop assembly in wacom-bridge\bin first.
python -m PyInstaller --noconfirm --clean --windowed --onedir --name IthuteSign --paths app app\main.py || exit /b 1
if exist wacom-bridge\bin\STUCapture.exe if not exist wacom-bridge\bin\Interop.wgssSTU.dll (echo ERROR: STU bridge interop dependency missing. & exit /b 1)
if /I "%~1"=="--release" if not exist wacom-bridge\bin\STUCapture.exe (echo ERROR: Production bridge missing. & exit /b 1)
if /I "%~1"=="--release" if not exist wacom-bridge\bin\Interop.wgssSTU.dll (echo ERROR: Wacom interop DLL missing. & exit /b 1)
if exist wacom-bridge\bin\STUCapture.exe (
  if not exist dist\IthuteSign\wacom-bridge mkdir dist\IthuteSign\wacom-bridge
  copy /Y wacom-bridge\bin\STUCapture.exe dist\IthuteSign\wacom-bridge\ || exit /b 1
  if exist wacom-bridge\bin\Interop.wgssSTU.dll copy /Y wacom-bridge\bin\Interop.wgssSTU.dll dist\IthuteSign\wacom-bridge\ || exit /b 1
  if exist wacom-bridge\branding\ithute-logo.png (
    if not exist dist\IthuteSign\wacom-bridge\branding mkdir dist\IthuteSign\wacom-bridge\branding
    copy /Y wacom-bridge\branding\ithute-logo.png dist\IthuteSign\wacom-bridge\branding\ || exit /b 1
  )
  echo STU capture bridge packaged.
) else (
  if /I "%~1"=="--release" (echo ERROR: Cannot build release without STU bridge. Follow README SDK steps. & exit /b 1)
  echo WARNING: STU bridge not built. Mouse test mode ONLY. Do not deploy as a signing workstation.
)
if /I "%~1"=="--release" (
  if not exist wacom-bridge\bin\STUCapture.exe exit /b 1
  if not exist dist\IthuteSign\wacom-bridge\STUCapture.exe exit /b 1
  >dist\IthuteSign\release-mode.flag echo STU-only release mode
)
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "PATH=%ProgramFiles(x86)%\Inno Setup 6;%PATH%"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "PATH=%ProgramFiles%\Inno Setup 6;%PATH%"
where iscc >nul 2>&1
if errorlevel 1 (
  if /I "%~1"=="--release" (echo ERROR: Inno Setup 6 ISCC missing for release build. & exit /b 1)
  echo Optional: install Inno Setup 6 to build Setup.exe and rerun this script.
) else (
  iscc installer\IthuteSign.iss || exit /b 1
)
echo Build complete. Check dist\IthuteSign\IthuteSign.exe
exit /b 0
