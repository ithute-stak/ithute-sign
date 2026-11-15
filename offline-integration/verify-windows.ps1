$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'IthuteSign offline verification — no deployment or GitHub changes'
dotnet --info
if ($LASTEXITCODE -ne 0) { throw 'dotnet SDK unavailable' }
dotnet restore ./tests/OfflineIntegration.Tests.csproj
if ($LASTEXITCODE -ne 0) { throw 'Restore failed' }
dotnet test ./tests/OfflineIntegration.Tests.csproj -c Release --no-restore
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
dotnet build ./src/OfflineIntegration.csproj -c Release --no-restore
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Host 'Offline verification passed. Hardware and server integration still require separate validation.'