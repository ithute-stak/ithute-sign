#!/usr/bin/env bash
# IthuteSign Ubuntu installer. Run as your normal desktop user.
set -Eeuo pipefail
if [[ $(id -u) -eq 0 ]]; then echo "Run as your desktop user, not root." >&2; exit 1; fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/ithute-sign"
[[ -f "$APP/requirements.txt" && -f "$APP/app/main.py" ]] || { echo "IthuteSign source tree not found" >&2; exit 1; }
command -v apt-get >/dev/null || { echo "Ubuntu/apt required" >&2; exit 1; }
command -v sudo >/dev/null || { echo "sudo required" >&2; exit 1; }
LOGDIR="${XDG_STATE_HOME:-$HOME/.local/state}/ithutesign"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
trap 'echo "Installation failed at line $LINENO. Log: $LOG" >&2' ERR
echo "Installing IthuteSign from $ROOT"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip openjdk-17-jdk \
  libegl1 libopengl0 libxkbcommon-x11-0 libgl1 libusb-1.0-0 \
  desktop-file-utils ca-certificates
if [[ ! -x "$APP/.venv/bin/python" ]]; then python3 -m venv "$APP/.venv"; fi
"$APP/.venv/bin/python" -m pip install --upgrade pip
"$APP/.venv/bin/python" -m pip install -r "$APP/requirements.txt"
"$APP/.venv/bin/python" -m py_compile "$APP/app/main.py" "$APP/app/loanhub.py" "$APP/app/loanhub_preflight_dialog.py"
"$APP/.venv/bin/python" -m unittest discover -s "$APP/tests" -p 'test_loanhub_signing_safety.py' -v
SDK="${WACOM_STU_SDK_LINUX:-$HOME/wacom-stu-sdk/sdk-extracted/Linux}"
if [[ -f "$SDK/any/wgssSTU.jar" && -d "$SDK/x86_64" ]]; then
  WACOM_STU_SDK_LINUX="$SDK" bash "$APP/wacom-bridge/linux/check-compile.sh"
else
  echo "NOTICE: Wacom SDK not installed. Install vendor SDK separately before tablet signing."
fi
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$BIN" "$DESKTOP"
printf -v QAPP '%q' "$APP"
cat > "$BIN/ithutesign" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
APP=$QAPP
cd "\$APP"
if [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then export QT_QPA_PLATFORM=wayland
elif [[ -n "\${DISPLAY:-}" ]]; then export QT_QPA_PLATFORM=xcb; fi
exec "\$APP/.venv/bin/python" -B "\$APP/app/main.py" "\$@"
LAUNCHER
chmod 755 "$BIN/ithutesign"
cat > "$DESKTOP/ithutesign.desktop" <<DESKTOPFILE
[Desktop Entry]
Version=1.0
Type=Application
Name=IthuteSign
GenericName=Offline Document Signing
Comment=LoanHub PDF signing with Wacom STU-540
Exec=$BIN/ithutesign
Icon=accessories-text-editor
Terminal=false
Categories=Office;
StartupNotify=true
DESKTOPFILE
chmod 644 "$DESKTOP/ithutesign.desktop"
desktop-file-validate "$DESKTOP/ithutesign.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$DESKTOP" || true
echo "IthuteSign installed. Open it from Ubuntu's application menu."
echo "Log: $LOG"
