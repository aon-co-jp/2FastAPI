#!/usr/bin/env bash
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
dpkg -r 2fastapi >/dev/null 2>&1 || true
sed -i 's/\r$//' /mnt/f/2FastAPI/installer/*.sh
HOME=/home/norukia bash /mnt/f/2FastAPI/installer/wsl-deb-check.sh 2>&1 | tail -14
ls /usr/bin/2fastapi /usr/share/doc/2fastapi 2>&1 | head -3
