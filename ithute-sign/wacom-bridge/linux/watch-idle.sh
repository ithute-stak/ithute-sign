#!/usr/bin/env bash
# Optional foreground monitor: restores IthuteSign branding on STU-540 connection.
# Start with: bash wacom-bridge/linux/watch-idle.sh
set -uo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v lsusb >/dev/null 2>&1; then
  echo "lsusb is required (install usbutils)." >&2
  exit 11
fi
if ! command -v flock >/dev/null 2>&1; then
  echo "flock is required (util-linux)." >&2
  exit 11
fi
echo "IthuteSign idle watcher running; Ctrl+C to stop."
ready=0
while true; do
  if lsusb -d 056a:00a8 | grep -q .; then
    if (( ! ready )); then
      # A busy signature session returns 75; retry without touching the pad.
      if ITHUTESIGN_LOCK_NONBLOCK=1 "$HERE/STUCapture" --idle; then
        ready=1
        echo "STU-540 branded idle screen restored."
      else
        result=$?
        if (( result != 75 )); then
          echo "Idle restoration failed (exit $result); retrying." >&2
        fi
      fi
    fi
  else
    if (( ready )); then echo "STU-540 disconnected; awaiting reconnection."; fi
    ready=0
  fi
  sleep 2
done
