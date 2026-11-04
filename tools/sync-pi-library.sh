#!/usr/bin/env bash
# Copy public themes and an optional ignored private slideshow library to Pi storage.
# Usage: tools/sync-pi-library.sh <user@pi-host> [private-theme-folder] [private-media-folder]
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
  echo "usage: $0 <user@pi-host> [private-theme-folder] [private-media-folder]" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
REMOTE=$1
PRIVATE_THEME=${2:-}
PRIVATE_MEDIA=${3:-}
DESTINATION=/mnt/storage/clean-tv

command -v rsync >/dev/null 2>&1 || { echo "rsync is required" >&2; exit 2; }

ssh "$REMOTE" "install -d -m 0700 '$DESTINATION' '$DESTINATION/themes' '$DESTINATION/themes/private' '$DESTINATION/private-media'; install -d -m 0755 '$DESTINATION/themes/public'"
rsync -a --exclude .DS_Store "$ROOT/theme-library/" "$REMOTE:$DESTINATION/themes/public/"

if [ -n "$PRIVATE_THEME" ]; then
  [ -d "$PRIVATE_THEME" ] || { echo "private theme folder not found: $PRIVATE_THEME" >&2; exit 2; }
  rsync -a --exclude .DS_Store "$PRIVATE_THEME/" "$REMOTE:$DESTINATION/themes/private/the-darkos/"
fi
if [ -n "$PRIVATE_MEDIA" ]; then
  [ -d "$PRIVATE_MEDIA" ] || { echo "private media folder not found: $PRIVATE_MEDIA" >&2; exit 2; }
  rsync -a --exclude .DS_Store "$PRIVATE_MEDIA/" "$REMOTE:$DESTINATION/private-media/the-darkos/"
fi

ssh "$REMOTE" "chmod -R go-rwx '$DESTINATION/themes/private' '$DESTINATION/private-media'"
echo "Pi theme library synchronized. Private folders remain owner-only and outside Git."
