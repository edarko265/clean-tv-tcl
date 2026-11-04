#!/usr/bin/env bash
# Privacy-first phone remote: a temporary LAN web UI backed by Android TV Remote Protocol v2.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/work/phone-remote"
VENV="$DATA/venv"
PY="$VENV/bin/python"
DEPS_MARKER="$DATA/dependencies-v1"

mkdir -p "$DATA"
chmod 700 "$DATA" 2>/dev/null || true
if [ ! -x "$PY" ]; then
  python3 -m venv "$VENV"
fi
if [ ! -f "$DEPS_MARKER" ] || ! "$PY" -c 'import importlib.metadata as m; raise SystemExit(m.version("androidtvremote2") != "0.3.2")' 2>/dev/null; then
  "$PY" -m pip install --disable-pip-version-check --upgrade -r "$ROOT/tools/requirements-phone-remote.txt"
  : > "$DEPS_MARKER"
fi

has_tv=0
for word in "$@"; do
  case "$word" in
    --tv|--tv=*|-h|--help) has_tv=1 ;;
  esac
done
if [ "$has_tv" = 0 ]; then
  : "${TV_HOST:?pass --tv <address> or set TV_HOST}"
  set -- --tv "${TV_HOST%%:*}" "$@"
fi

exec "$PY" -I "$ROOT/tools/phone_remote.py" --data-dir "$DATA" "$@"
