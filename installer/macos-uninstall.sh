#!/bin/sh
# Removes what the 2FastAPI .pkg installed (a .pkg has no uninstaller of its own). Safe to run twice.
H="${HOME:-$(eval echo ~)}"
L="$H/.local/bin/2fastapi"
[ -L "$L" ] && [ "$(readlink "$L")" = "$H/Library/2FastAPI/2fastapi" ] && rm -f "$L"
pkgutil --forget jp.aon-co.2fastapi >/dev/null 2>&1 || true
D="$H/Library/2FastAPI"
cd "$H" && rm -rf "$D"
echo "2FastAPI removed (your ~/.2fastapi state folder is kept; delete it by hand if you want)."
