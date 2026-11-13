# Verifies an IthuteSign Windows release payload before distribution.
# Usage: pwsh -File packaging/Verify-IthuteSignBundle.ps1 -AppDirectory <published-app-folder>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$AppDirectory)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $AppDirectory).Path
$required = @(
  'IthuteSign.Modern.exe',
  'wacom-bridge/STUCapture.exe',
  'wacom-connector/loanhub-wacom-connector.exe'
)
foreach ($relative in $required) {
  $file = Join-Path $root $relative
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
    throw "Release bundle incomplete: missing $relative"
  }
  $item = Get-Item -LiteralPath $file
  if ($item.Length -le 0) { throw "Release bundle contains an empty file: $relative" }
  $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
  Write-Output "$relative | $($item.Length) bytes | SHA256 $hash"
}
# Do not distribute workstation private keys or credentials in the installer.
$forbidden = @('*.pem','*.key','*private*.json','*credentials*.json','*token*.json')
foreach ($pattern in $forbidden) {
  $matches = @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter $pattern)
  if ($matches.Count -gt 0) {
    throw "Release bundle may contain sensitive key material matching $pattern"
  }
}
Write-Output 'Bundle payload checks passed. This is NOT a Windows build, device enrollment, or signing test.'
