#!/usr/bin/env bash
# WSL: PyInstaller binary -> .deb -> dpkg -i / run / dpkg -r (needs root or sudo). Local helper for the CI "deb" job.
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/bin:/bin"
. "$HOME/2fa-venv/bin/activate"
cd "$(dirname "$0")/.."
uv pip install -q pyinstaller >/dev/null 2>&1 || python -m pip install -q pyinstaller
W=/tmp/2fa-deb-build; rm -rf "$W"; mkdir -p "$W"
VER=$(python -c "import re;print(re.search(r'__version__ = \"(.+?)\"', open('src/tofastapi/__init__.py').read()).group(1))")
PYTHONPATH="$PWD/src" python -m PyInstaller --noconfirm --onefile --name 2fastapi --distpath "$W/dist" --workpath "$W/work" --specpath "$W" --collect-submodules libcst --collect-submodules tofastapi --hidden-import tofastapi._autoupdate --paths src installer/cli_entry.py >/dev/null 2>&1
ARCH=$(dpkg --print-architecture)
DEB=$(bash installer/build-deb.sh "$W/dist/2fastapi" "$VER" "$ARCH" "$W/out")
dpkg-deb -I "$DEB" | head -12
bash installer/test-deb.sh "$DEB"
