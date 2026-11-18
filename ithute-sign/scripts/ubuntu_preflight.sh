#!/usr/bin/env bash
# Read-only Ubuntu workstation preflight for IthuteSign.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
issues=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then printf '[OK] %s\n' "$label"
  else printf '[MISSING] %s\n' "$label"; issues=$((issues+1)); fi
}
printf 'IthuteSign Ubuntu preflight\n'
printf 'Repository: %s\n' "$ROOT"
check 'Python 3 available' command -v python3
check 'Git available' command -v git
check 'Java available (Linux Wacom bridge)' command -v java
check 'USB listing tool available (lsusb)' command -v lsusb
check 'Python virtual environment' test -x "$ROOT/.venv/bin/python"
check 'Application entry point' test -f "$ROOT/app/main.py"
if [ -x "$ROOT/.venv/bin/python" ]; then
  check 'PySide6 import' "$ROOT/.venv/bin/python" -c 'import PySide6'
  check 'PyMuPDF import' "$ROOT/.venv/bin/python" -c 'import fitz'
fi
if command -v lsusb >/dev/null 2>&1; then
  printf '\nUSB devices matching Wacom (informational):\n'
  lsusb | grep -i wacom || printf 'No Wacom USB device listed; check cable/permissions.\n'
fi
printf '\nPreflight missing prerequisites: %d\n' "$issues"
printf 'NOTE: Device detection alone does not prove SDK bridge or pen capture works.\n'
if [ "$issues" -gt 0 ]; then exit 1; fi
