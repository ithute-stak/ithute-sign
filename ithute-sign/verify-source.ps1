$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root 'wacom-bridge\STUCapture.cs'
if (-not (Test-Path $source)) { throw "Missing source file: $source" }
$text = [System.IO.File]::ReadAllText($source)
if ($text -notmatch 'using Rectangle\s*=\s*System\.Drawing\.Rectangle\s*;') { throw 'Missing Rectangle alias.' }
if ($text -match 'catch\s*\(\s*ObjectDisposedException\s*\)') { throw 'Outdated source: CS0160 catch remains.' }
Write-Host 'IthuteSign source checks passed.'
