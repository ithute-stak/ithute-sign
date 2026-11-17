#!/usr/bin/env bash
# Opt-in per-user service for STU-540 idle branding. No sudo or firmware changes.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE="$SERVICE_DIR/ithutesign-stu540-idle.service"
if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd user services are unavailable on this system." >&2
  exit 1
fi
if ! command -v lsusb >/dev/null 2>&1 || ! command -v flock >/dev/null 2>&1; then
  echo "Install usbutils (lsusb) and util-linux (flock) before enabling the service." >&2
  exit 1
fi
if [[ "${1:-}" == "--remove" ]]; then
  systemctl --user disable --now ithutesign-stu540-idle.service 2>/dev/null || true
  rm -f -- "$SERVICE"
  systemctl --user daemon-reload
  echo "IthuteSign idle watcher service removed."
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo "Usage: bash install-idle-service.sh [--remove]" >&2
  exit 2
fi
if [[ "$HERE" == *%* || "$HERE" == *'"'* || "$HERE" == *$'\n'* ]]; then
  echo "Unsupported characters in checkout path." >&2
  exit 2
fi
mkdir -p "$SERVICE_DIR"
cat > "$SERVICE" <<UNIT
[Unit]
Description=IthuteSign Wacom STU-540 idle branding watcher
Documentation=https://github.com/ithute-stak/ithute-sign
After=default.target

[Service]
Type=simple
ExecStart=/usr/bin/bash "$HERE/watch-idle.sh"
Restart=on-failure
RestartSec=5
TimeoutStopSec=10

[Install]
WantedBy=default.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now ithutesign-stu540-idle.service
echo "IthuteSign idle watcher enabled for this user's login sessions."
echo "Status: systemctl --user status ithutesign-stu540-idle.service"
echo "Logs: journalctl --user -u ithutesign-stu540-idle.service -f"
