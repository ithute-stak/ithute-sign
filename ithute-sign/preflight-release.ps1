$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root 'dist\IthuteSign'
$required = @(
  (Join-Path $dist 'IthuteSign.exe'),
  (Join-Path $dist 'release-mode.flag'),
  (Join-Path $dist 'wacom-bridge\STUCapture.exe'),
  (Join-Path $dist 'wacom-bridge\Interop.wgssSTU.dll'),
  (Join-Path $root 'dist\installer\IthuteSign-Setup.exe')
)
foreach ($file in $required) {
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
    throw "Release preflight failed: missing $file"
  }
  if ((Get-Item -LiteralPath $file).Length -eq 0) {
    throw "Release preflight failed: empty $file"
  }
}
Write-Host 'IthuteSign release preflight PASSED (files only).'
Write-Host 'Hardware signature acceptance is still required.'


# A setup file from an earlier build must not be accepted as the current release.
$setup = Join-Path $root 'dist\installer\IthuteSign-Setup.exe'
if ((Get-Item -LiteralPath $setup).LastWriteTimeUtc -lt (Get-Date).ToUniversalTime().AddHours(-2)) {
  throw "Release preflight failed: installer is not from a recent build"
}
Write-Host ('Installer SHA-256: ' + (Get-FileHash -Algorithm SHA256 -LiteralPath $setup).Hash)
