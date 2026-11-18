#!/usr/bin/env bash
# Compile the STU bridge without opening the tablet or capturing a signature.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SDK="${WACOM_STU_SDK_LINUX:-$HOME/wacom-stu-sdk/sdk-extracted/Linux}"
JAR="$SDK/any/wgssSTU.jar"
if [[ ! -f "$JAR" ]]; then
  printf 'Wacom Java SDK not found: %s\n' "$JAR" >&2
  exit 11
fi
command -v javac >/dev/null || { echo "Java compiler (javac) missing" >&2; exit 11; }
BUILD="$(mktemp -d)"
trap 'rm -rf -- "$BUILD"' EXIT
javac -cp "$JAR" -d "$BUILD" "$HERE/STUCapture.java"
test -f "$BUILD/STUCapture.class"
echo "STU-540 Java bridge compilation PASSED (no tablet accessed)"
