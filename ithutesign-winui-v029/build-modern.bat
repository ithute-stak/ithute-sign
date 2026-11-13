@echo off
setlocal
cd /d "%~dp0"
where dotnet >nul 2>nul || (echo Install .NET 8 SDK and Visual Studio 2022 WinUI 3 workload first. & exit /b 1)
dotnet restore "IthuteSign.Modern\IthuteSign.Modern.csproj" -p:Platform=x64 || exit /b 1
dotnet build "IthuteSign.Modern\IthuteSign.Modern.csproj" -c Release -p:Platform=x64 --no-restore -v:normal || exit /b 1
echo Build finished. Check IthuteSign.Modern\bin\x64\Release
