#!/usr/bin/env bash
# usage: build-deb.sh <path to the PyInstaller binary "2fastapi"> <version> <amd64|arm64> <out dir>
# Builds 2fastapi_<version>_<arch>.deb  (installs /usr/bin/2fastapi and /usr/share/doc/2fastapi/*).
set -euo pipefail
BIN="$1"; VER="$2"; ARCH="$3"; OUT="$4"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
install -D -m 0755 "$BIN" "$ROOT/usr/bin/2fastapi"
install -D -m 0644 "$HERE/LICENSE" "$ROOT/usr/share/doc/2fastapi/copyright"
install -D -m 0644 "$HERE/README.md" "$ROOT/usr/share/doc/2fastapi/README.md"
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CTL
Package: 2fastapi
Version: $VER
Section: devel
Priority: optional
Architecture: $ARCH
Installed-Size: $SIZE
Maintainer: aon-co-jp <noreply@users.noreply.github.com>
Homepage: https://github.com/aon-co-jp/2FastAPI
Description: Convert Flask / Django (DRF) projects to FastAPI (MFastAPI compatible)
 Command line build of 2FastAPI, bundled with its own Python runtime.
 Updates are never applied automatically: a newer release is only announced
 on stderr (set TOFASTAPI_NO_UPDATE=1 to silence it); install the new .deb.
CTL
mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT/2fastapi_${VER}_${ARCH}.deb" >/dev/null
echo "$OUT/2fastapi_${VER}_${ARCH}.deb"
