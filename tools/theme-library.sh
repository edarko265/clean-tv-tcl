#!/usr/bin/env bash
# Install offline theme packs into the launcher's app-private library. Once installed, Launcher settings >
# Theme gallery switches them with the remote; no computer or network is needed for each change.
# Usage: TV_HOST=<tv-ip> tools/theme-library.sh [theme-library-folder]
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LIBRARY=${1:-$ROOT/theme-library}
if [ "$#" -gt 1 ]; then
  echo "usage: TV_HOST=<tv-ip> $0 [theme-library-folder]" >&2
  exit 2
fi
if [ -z "${TV_HOST:-}" ]; then
  echo "set TV_HOST to the TV address. Nothing was sent to the TV." >&2
  exit 2
fi
if [ ! -f "$LIBRARY/catalog.json" ]; then
  echo "no catalog.json in $LIBRARY. Nothing was sent to the TV." >&2
  exit 2
fi

PY=$ROOT/tools/venv/bin/python
[ -x "$PY" ] || PY=$ROOT/tools/venv/Scripts/python.exe
[ -x "$PY" ] || { echo "tools/venv is required. Nothing was sent to the TV." >&2; exit 2; }

IDS=$(
  "$PY" -I - "$LIBRARY" <<'PY'
import json, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
try:
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
except (OSError, ValueError) as error:
    raise SystemExit(f"invalid theme catalog: {error}")
items = catalog.get("themes") if isinstance(catalog, dict) else None
if not isinstance(items, list) or not items:
    raise SystemExit("theme catalog has no themes")
seen = set()
for item in items:
    if not isinstance(item, dict):
        raise SystemExit("theme catalog entries must be objects")
    theme_id = item.get("id", "")
    if not isinstance(theme_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", theme_id):
        raise SystemExit(f"unsafe theme id: {theme_id!r}")
    if theme_id in seen:
        raise SystemExit(f"duplicate theme id: {theme_id}")
    seen.add(theme_id)
    folder = root / theme_id
    config = folder / "config.json"
    wallpaper = folder / "wallpaper.jpg"
    try:
        parsed = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"invalid {theme_id}/config.json: {error}")
    if not isinstance(parsed, dict) or not wallpaper.is_file() or wallpaper.stat().st_size <= 0:
        raise SystemExit(f"{theme_id} needs an object config.json and nonempty wallpaper.jpg")
    print(theme_id)
PY
) || { echo "Nothing was sent to the TV." >&2; exit 2; }

tv() { "$PY" -I "$ROOT/tools/tv.py" "$@"; }
URI=content://com.gathin.tvhome.theme/library
TMP=/data/local/tmp/cyt-theme-library

local_md5() {
  "$PY" -I -c 'import hashlib,sys; print(hashlib.md5(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
}

push_file() {
  local local_file=$1
  local relative=$2
  local stage="$TMP-${relative//\//-}"
  local uri="$URI/$relative"
  "$PY" -I "$ROOT/tools/b64push.py" "$local_file" "$stage" >/dev/null
  local result
  result=$(tv "o=\$(content write --uri $uri < $stage 2>&1); rc=\$?; rm -f $stage; printf '%s' \"\$o\"; exit \$rc")
  case "$result" in
    *"Error while accessing provider"*|*Exception*|*"Unsupported operation"*)
      echo "could not write $relative through the launcher provider: $result" >&2
      return 1 ;;
  esac
  local expected actual
  expected=$(local_md5 "$local_file")
  actual=$(tv "content read --uri $uri | md5sum" | awk '{print $1}')
  if [ "$expected" != "$actual" ]; then
    echo "theme library verification failed for $relative" >&2
    return 1
  fi
}

for id in $IDS; do
  echo "installing $id"
  push_file "$LIBRARY/$id/config.json" "$id/config.json"
  push_file "$LIBRARY/$id/wallpaper.jpg" "$id/wallpaper.jpg"
done
# Publish the catalogue last: the TV never offers a pack whose two files did not verify.
push_file "$LIBRARY/catalog.json" "catalog.json"
echo "Installed $(printf '%s\n' $IDS | wc -l | tr -d ' ') offline themes. Open Launcher settings > Theme gallery."
