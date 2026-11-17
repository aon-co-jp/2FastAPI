#!/usr/bin/env bash
# usage: test-pkg.sh <pkg>   (macOS): pkgutil --expand -> installer -pkg (current user) -> run -> uninstall -> nothing left.
set -euo pipefail
PKG="$1"
export TOFASTAPI_NO_UPDATE=1
X="$(mktemp -d)/expanded"; pkgutil --expand "$PKG" "$X"; ls "$X"
test -f "$X/Distribution"
installer -pkg "$PKG" -target CurrentUserHomeDirectory -verboseR
BIN="$HOME/Library/2FastAPI/2fastapi"
test -x "$BIN"; test -L "$HOME/.local/bin/2fastapi"
"$BIN" --version
"$HOME/.local/bin/2fastapi" --version
d=$(mktemp -d); printf 'from flask import Flask\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "hi"\n' > "$d/app.py"
"$BIN" flask "$d/app.py" | grep -q "FastAPI"
sh "$HOME/Library/2FastAPI/uninstall.sh"
test ! -e "$HOME/Library/2FastAPI" && test ! -L "$HOME/.local/bin/2fastapi" && test ! -e "$HOME/.local/bin/2fastapi"
echo "pkg OK"
