#!/usr/bin/env bash
# Build a TV-safe, metadata-free wallpaper collection from private photos and short videos.
# The input and output folders should both be ignored by Git. Nothing leaves this computer.
#
# Usage: tools/build-private-slideshow.sh <private media folder> <empty wallpapers folder>
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <private media folder> <empty wallpapers folder>" >&2
  exit 2
fi

SOURCE=$1
DESTINATION=$2

if [ ! -d "$SOURCE" ]; then
  echo "private media folder not found: $SOURCE" >&2
  exit 2
fi

command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg is required" >&2; exit 2; }
command -v ffprobe >/dev/null 2>&1 || { echo "ffprobe is required" >&2; exit 2; }

mkdir -p "$DESTINATION"
if find "$DESTINATION" -mindepth 1 ! -name captions.txt -print -quit | grep -q .; then
  echo "output folder must be empty except for captions.txt: $DESTINATION" >&2
  exit 2
fi

render_frame() {
  local source_file=$1
  local destination_file=$2
  local seek=${3:-}
  local filter
  filter="[0:v]split=2[background][foreground];\
[background]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=24:12[soft];\
[foreground]scale=1920:1080:force_original_aspect_ratio=decrease[photo];\
[soft][photo]overlay=(W-w)/2:(H-h)/2,format=yuvj420p"

  if [ -n "$seek" ]; then
    ffmpeg -hide_banner -loglevel error -y -ss "$seek" -i "$source_file" \
      -filter_complex "$filter" -frames:v 1 -q:v 5 -map_metadata -1 "$destination_file"
  else
    ffmpeg -hide_banner -loglevel error -y -i "$source_file" \
      -filter_complex "$filter" -frames:v 1 -q:v 5 -map_metadata -1 "$destination_file"
  fi
}

counter=1
while IFS= read -r -d '' media; do
  extension=${media##*.}
  extension=$(printf '%s' "$extension" | tr '[:upper:]' '[:lower:]')
  case "$extension" in
    jpg|jpeg|png|webp|heic|heif)
      output=$(printf '%03d.jpg' "$counter")
      render_frame "$media" "$DESTINATION/$output"
      counter=$((counter + 1))
      ;;
    mov|mp4|m4v|webm|mkv)
      duration=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$media")
      for fraction in 0.25 0.50 0.75; do
        seek=$(awk -v duration="$duration" -v fraction="$fraction" 'BEGIN { printf "%.3f", duration * fraction }')
        output=$(printf '%03d.jpg' "$counter")
        render_frame "$media" "$DESTINATION/$output" "$seek"
        counter=$((counter + 1))
      done
      ;;
  esac
done < <(find "$SOURCE" -maxdepth 1 -type f -print0)

count=$((counter - 1))
if [ "$count" -eq 0 ]; then
  echo "no supported photos or videos found in $SOURCE" >&2
  exit 1
fi

echo "created $count private, metadata-free 1080p slideshow frames in $DESTINATION"
