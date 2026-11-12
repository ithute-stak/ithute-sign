param([switch]$SkipInstall, [string]$InteropPath = "")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$project = Join-Path $root 'wacom-bridge\STUCapture.csproj'
$destination = Join-Path $root 'wacom-bridge\lib\Interop.wgssSTU.dll'
try {
    if (-not (Test-Path $project)) { throw "Missing project: $project" }
    if (-not (Test-Path $destination)) {
        $candidates = @()
        if ($InteropPath) { $candidates += $InteropPath }
        if ($env:WACOM_STU_INTEROP_DLL) { $candidates += $env:WACOM_STU_INTEROP_DLL }
        $x86 = [Environment]::GetFolderPath('ProgramFilesX86')
        foreach ($base in @($env:ProgramFiles, $x86, 'C:\Wacom', 'C:\Wacom-SDK')) {
            if ($base -and (Test-Path $base)) {
                $candidates += @(Get-ChildItem -Path $base -Filter 'Interop.wgssSTU.dll' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
            }
        }
        $source = $candidates | Where-Object { $_ -and (Test-Path $_ -PathType Leaf) } | Select-Object -First 1
        if (-not $source) {
            throw "Wacom interop DLL not found. Locate Interop.wgssSTU.dll from your official Wacom STU SDK, then run: powershell -ExecutionPolicy Bypass -File .\setup-wacom.ps1 -InteropPath 'C:\path\Interop.wgssSTU.dll'"
        }
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
        Write-Host "Using Wacom SDK interop: $source"
    }
    $command = Get-Command msbuild.exe -ErrorAction SilentlyContinue
    $msbuild = if ($command) { $command.Source } else { $null }
    if (-not $msbuild) {
        $vswhere = Join-Path ([Environment]::GetFolderPath('ProgramFilesX86')) 'Microsoft Visual Studio\Installer\vswhere.exe'
        if (Test-Path $vswhere) {
            $msbuild = & $vswhere -latest -requires Microsoft.Component.MSBuild -find 'MSBuild\**\Bin\MSBuild.exe' | Select-Object -First 1
        }
    }
    if (-not $msbuild) { throw "MSBuild not found. Install Visual Studio Build Tools with .NET Framework 4.8 targeting pack and MSBuild." }
    Write-Host "Building STU bridge with $msbuild"
    & $msbuild $project '/t:Build' '/p:Configuration=Release' '/p:Platform=x86' '/verbosity:minimal'
    if ($LASTEXITCODE -ne 0) { throw "STU bridge compilation failed (exit $LASTEXITCODE). Copy compiler errors for diagnosis." }
    $exe = Join-Path $root 'wacom-bridge\bin\STUCapture.exe'
    if (-not (Test-Path $exe)) { throw "Build finished without expected executable: $exe" }
    Write-Host "Built: $exe"
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
