#!/usr/bin/env bash
# Per-user Linux installation of the IthuteSign desktop app.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}/ithutesign"
APPLICATIONS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
BIN="$HOME/.local/bin"
DESKTOP="$APPLICATIONS/ithutesign.desktop"
if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "$DESKTOP" "$BIN/ithutesign" "$ICONS/ithutesign.svg" "$HOME/Desktop/ithutesign.desktop"
  rm -rf -- "$PREFIX"
  echo "IthuteSign application removed (documents outside installation unchanged)."
  exit 0
fi
if [[ $# -ne 0 ]]; then echo "Usage: bash packaging/linux/install.sh [--uninstall]" >&2; exit 2; fi
command -v python3 >/dev/null || { echo "python3 missing" >&2; exit 1; }
command -v flock >/dev/null || { echo "flock missing (util-linux)" >&2; exit 1; }
# Stage installation before replacing current files. No system-wide writes.
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/ithutesign-install.XXXXXXXX")"
trap 'rm -rf -- "$STAGE"' EXIT
python3 -m venv "$STAGE/venv"
"$STAGE/venv/bin/python" -m pip install -r "$ROOT/requirements.txt"
mkdir -p "$STAGE/app" "$STAGE/wacom-bridge"
cp -a "$ROOT/app/." "$STAGE/app/"
cp -a "$ROOT/wacom-bridge/." "$STAGE/wacom-bridge/"
cp "$ROOT/requirements.txt" "$STAGE/requirements.txt"
mkdir -p "$PREFIX" "$APPLICATIONS" "$ICONS" "$BIN"
# Keep existing install until dependencies have been prepared successfully.
if [[ -d "$PREFIX/venv" ]]; then rm -rf -- "$PREFIX/venv"; fi
cp -a "$STAGE/venv" "$PREFIX/venv"
cp -a "$STAGE/app" "$PREFIX/"
cp -a "$STAGE/wacom-bridge" "$PREFIX/"
cp "$STAGE/requirements.txt" "$PREFIX/requirements.txt"
cp "$HERE/ithutesign.svg" "$ICONS/ithutesign.svg"
cat > "$BIN/ithutesign" <<'RUN'
#!/usr/bin/env bash
set -euo pipefail
ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/ithutesign"
cd "$ROOT"
exec "$ROOT/venv/bin/python" "$ROOT/app/main.py" "$@"
RUN
chmod +x "$BIN/ithutesign"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=IthuteSign
GenericName=Document Signing
Comment=Secure document signing with Wacom STU-540
Exec=$BIN/ithutesign
Icon=ithutesign
Terminal=false
Categories=Office;Utility;
StartupNotify=true
EOF
chmod 644 "$DESKTOP"
# Trust only the desktop shortcut installed by this script.
if [[ -d "$HOME/Desktop" ]]; then
  cp -- "$DESKTOP" "$HOME/Desktop/ithutesign.desktop"
  chmod +x "$HOME/Desktop/ithutesign.desktop"
  if command -v gio >/dev/null 2>&1; then
    gio set "$HOME/Desktop/ithutesign.desktop" metadata::trusted true || true
  fi
fi
if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$APPLICATIONS" || true; fi
echo "IthuteSign installed. Find it in your application launcher as IthuteSign."
echo "Desktop shortcut: cp '$DESKTOP' '$HOME/Desktop/ithutesign.desktop' (if desired)."
echo "Wacom Linux SDK must remain installed in the configured SDK directory."
