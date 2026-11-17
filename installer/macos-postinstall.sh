#!/bin/sh
# Runs as the installing user: put 2fastapi on the PATH for the usual ~/.local/bin convention.
H="${HOME:-$(eval echo ~)}"
mkdir -p "$H/.local/bin"
ln -sf "$H/Library/2FastAPI/2fastapi" "$H/.local/bin/2fastapi"
exit 0
