#!/usr/bin/env bash
# usage: test-deb.sh <deb file>   (needs root: dpkg -i / -r). install -> run -> remove -> nothing left behind.
set -euo pipefail
DEB="$1"
export PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin"
SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
export TOFASTAPI_NO_UPDATE=1
trap '$SUDO dpkg -r 2fastapi >/dev/null 2>&1 || true' ERR
$SUDO dpkg -i "$DEB"
test -x /usr/bin/2fastapi
/usr/bin/2fastapi --version
dpkg -L 2fastapi > /tmp/2fastapi.files
d=$(mktemp -d); printf 'from flask import Flask\napp = Flask(__name__)\n\n@app.route("/")\ndef index():\n    return "hi"\n' > "$d/app.py"
/usr/bin/2fastapi flask "$d/app.py" | grep -q "FastAPI"
$SUDO dpkg -r 2fastapi
! dpkg -s 2fastapi 2>/dev/null | grep -q "Status: install ok installed"
for f in $(grep -v '^/\.$' /tmp/2fastapi.files | grep -E '^/(usr/bin|usr/share/doc)/2fastapi'); do
  if [ -e "$f" ] && [ ! -d "$f" ]; then echo "left behind: $f"; exit 1; fi
done
test ! -e /usr/bin/2fastapi && test ! -d /usr/share/doc/2fastapi
echo "deb OK"
