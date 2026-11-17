#!/usr/bin/env bash
# usage: build-pkg.sh <path to the PyInstaller binary "2fastapi"> <version> <x64|arm64> <out dir>
# Builds 2FastAPI-<version>-macos-<arch>.pkg that installs for the CURRENT USER (no admin rights):
#   ~/Library/2FastAPI/2fastapi, ~/Library/2FastAPI/uninstall.sh, and a symlink ~/.local/bin/2fastapi
set -euo pipefail
BIN="$1"; VER="$2"; ARCH="$3"; OUT="$4"
HERE="$(cd "$(dirname "$0")" && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
ROOT="$W/root"; SCR="$W/scripts"
mkdir -p "$ROOT" "$SCR" "$OUT"
install -m 0755 "$BIN" "$ROOT/2fastapi"
install -m 0755 "$HERE/macos-uninstall.sh" "$ROOT/uninstall.sh"
install -m 0644 "$HERE/../LICENSE" "$ROOT/LICENSE"
install -m 0755 "$HERE/macos-postinstall.sh" "$SCR/postinstall"
HOSTARCH=$([ "$ARCH" = arm64 ] && echo arm64 || echo x86_64)
pkgbuild --root "$ROOT" --identifier jp.aon-co.2fastapi --version "$VER" --install-location "Library/2FastAPI" --scripts "$SCR" "$W/component.pkg" >/dev/null
cat > "$W/distribution.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="2">
  <title>2FastAPI</title>
  <options customize="never" require-scripts="false" hostArchitectures="$HOSTARCH"/>
  <domains enable_anywhere="false" enable_currentUserHome="true" enable_localSystem="false"/>
  <choices-outline><line choice="default"><line choice="jp.aon-co.2fastapi"/></line></choices-outline>
  <choice id="default"/>
  <choice id="jp.aon-co.2fastapi" visible="false"><pkg-ref id="jp.aon-co.2fastapi"/></choice>
  <pkg-ref id="jp.aon-co.2fastapi" version="$VER" onConclusion="none">component.pkg</pkg-ref>
</installer-gui-script>
XML
PKG="$OUT/2FastAPI-$VER-macos-$ARCH.pkg"
productbuild --distribution "$W/distribution.xml" --package-path "$W" "$PKG" >/dev/null
echo "$PKG"
