#!/usr/bin/env bash
# Install the already-staged phone remote as a locked-down, LAN-only systemd service.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo: sudo ./install.sh <tv-ip>" >&2
  exit 2
fi
if [ "$#" -lt 1 ] || [ "$#" -gt 3 ] || ! [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "usage: sudo ./install.sh <tv-ip> [public-base-url] [wyoming-host:port]" >&2
  exit 2
fi

SOURCE="$(cd "$(dirname "$0")" && pwd)"
TARGET=/opt/clean-tv-remote
STATE=/var/lib/clean-tv-remote

if ! id clean-tv-remote >/dev/null 2>&1; then
  useradd --system --home-dir "$STATE" --shell /usr/sbin/nologin clean-tv-remote
fi
install -d -m 0755 "$TARGET/phone-remote"
install -d -o clean-tv-remote -g clean-tv-remote -m 0700 "$STATE"
install -m 0755 "$SOURCE/phone_remote.py" "$TARGET/phone_remote.py"
install -m 0644 "$SOURCE/requirements-phone-remote.txt" "$TARGET/requirements-phone-remote.txt"
install -m 0644 "$SOURCE/phone-remote/index.html" "$TARGET/phone-remote/index.html"
install -m 0644 "$SOURCE/phone-remote/manifest.webmanifest" "$TARGET/phone-remote/manifest.webmanifest"
install -m 0644 "$SOURCE/phone-remote/icon-192.png" "$TARGET/phone-remote/icon-192.png"
install -m 0644 "$SOURCE/phone-remote/icon-512.png" "$TARGET/phone-remote/icon-512.png"

if [ ! -x "$TARGET/venv/bin/python" ]; then
  python3 -m venv "$TARGET/venv"
fi
"$TARGET/venv/bin/python" -m pip install --disable-pip-version-check --upgrade \
  -r "$TARGET/requirements-phone-remote.txt"

{
  printf 'TV_HOST=%s\n' "$1"
  printf 'PUBLIC_BASE_URL=%s\n' "${2:-}"
  printf 'WYOMING_WHISPER=%s\n' "${3:-}"
  printf 'SERVICE_LINKS=%s\n' "$STATE/service-links.json"
} > /etc/clean-tv-remote
chmod 0600 /etc/clean-tv-remote
install -m 0644 "$SOURCE/clean-tv-remote.service" /etc/systemd/system/clean-tv-remote.service
systemctl daemon-reload
systemctl enable clean-tv-remote.service

echo "Installed. Pair in the foreground or copy an existing client certificate into $STATE, then start the service."
