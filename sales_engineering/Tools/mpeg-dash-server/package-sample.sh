#!/usr/bin/env bash
# Helper to trigger MPEG-DASH packaging for a given MP4 via the FastAPI backend.
# Usage: ./package-sample.sh [path-to-mp4] [--backend-url URL] [--stream-id ID]
#        [--dynamic] [--segment-duration SECONDS] [--window-size N] [--extra-window-size N]
#        [--segment-padding N] [--segment-template TEMPLATE] [--init-template TEMPLATE]
#        [--reencode] [--video-bitrate KBPS] [--audio-bitrate KBPS]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEDIA_ROOT="${MEDIA_ROOT:-$ROOT_DIR/media}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
MP4_PATH=""
STREAM_ID=""
DYNAMIC_MODE=0
SEGMENT_DURATION=""
WINDOW_SIZE=""
EXTRA_WINDOW_SIZE=""
SEGMENT_PADDING=""
SEGMENT_TEMPLATE=""
INIT_TEMPLATE=""
REENCODE=0
VIDEO_BITRATE=""
AUDIO_BITRATE=""

usage() {
  cat <<EOF
Usage: $0 [path-to-mp4] [--backend-url URL] [--stream-id ID]
        [--dynamic] [--segment-duration SECONDS] [--window-size N] [--extra-window-size N]
        [--segment-padding N] [--segment-template TEMPLATE] [--init-template TEMPLATE]
        [--reencode] [--video-bitrate KBPS] [--audio-bitrate KBPS]
Defaults:
  path       -> first positional argument, else MEDIA_ROOT/sample.mp4
  backend-url -> env BACKEND_URL or http://localhost:8000
  stream-id  -> derived from filename when omitted
  segment-duration -> 4 (when --dynamic or --reencode enabled)
  window-size / extra-window-size -> 6 (when --dynamic)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-url)
      BACKEND_URL="$2"
      shift 2
      ;;
    --stream-id)
      STREAM_ID="$2"
      shift 2
      ;;
    --dynamic)
      DYNAMIC_MODE=1
      shift
      ;;
    --segment-duration)
      SEGMENT_DURATION="$2"
      shift 2
      ;;
    --window-size)
      WINDOW_SIZE="$2"
      shift 2
      ;;
    --extra-window-size)
      EXTRA_WINDOW_SIZE="$2"
      shift 2
      ;;
    --segment-padding)
      SEGMENT_PADDING="$2"
      shift 2
      ;;
    --segment-template)
      SEGMENT_TEMPLATE="$2"
      shift 2
      ;;
    --init-template)
      INIT_TEMPLATE="$2"
      shift 2
      ;;
    --reencode)
      REENCODE=1
      shift
      ;;
    --video-bitrate)
      VIDEO_BITRATE="$2"
      shift 2
      ;;
    --audio-bitrate)
      AUDIO_BITRATE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      MP4_PATH="$1"
      shift
      ;;
  esac
done

if [[ -z "$MP4_PATH" ]]; then
  if [[ -f "$MEDIA_ROOT/sample.mp4" ]]; then
    MP4_PATH="$MEDIA_ROOT/sample.mp4"
  else
    echo "Error: MP4 path not provided and $MEDIA_ROOT/sample.mp4 not found." >&2
    exit 1
  fi
fi

if [[ ! -f "$MP4_PATH" ]]; then
  echo "Error: file '$MP4_PATH' does not exist." >&2
  exit 1
fi

if [[ "${MP4_PATH##*.}" != "mp4" ]]; then
  echo "Error: file must have .mp4 extension." >&2
  exit 1
fi

ABS_PATH="$(python3 - <<'PY'
import os, sys
print(os.path.abspath(sys.argv[1]))
PY
"$MP4_PATH")"

if [[ -z "$STREAM_ID" ]]; then
  BASENAME="$(basename "$ABS_PATH" .mp4)"
  STREAM_ID="sample-${BASENAME}"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is required for this helper script." >&2
  exit 1
fi

REQUEST_PAYLOAD=$(python3 - <<'PY'
import json, os

path = os.environ['ABS_MP4']
stream_id = os.environ['STREAM_ID']

payload: dict[str, object] = {'path': path}
if stream_id:
  payload['stream_id'] = stream_id

options: dict[str, object] = {}
if os.environ.get('DYNAMIC_MODE') == '1':
  options['mode'] = 'dynamic'
  seg = os.environ.get('SEGMENT_DURATION') or '4'
  options['segment_duration_seconds'] = float(seg)
  win = os.environ.get('WINDOW_SIZE') or '6'
  options['window_size'] = int(win)
  extra = os.environ.get('EXTRA_WINDOW_SIZE') or win
  options['extra_window_size'] = int(extra)
if os.environ.get('SEGMENT_PADDING'):
  options['segment_padding'] = int(os.environ['SEGMENT_PADDING'])
if os.environ.get('SEGMENT_TEMPLATE'):
  options['segment_template'] = os.environ['SEGMENT_TEMPLATE']
if os.environ.get('INIT_TEMPLATE'):
  options['init_segment_template'] = os.environ['INIT_TEMPLATE']
if os.environ.get('REENCODE') == '1':
  options['reencode'] = True
  vbr = os.environ.get('VIDEO_BITRATE') or '5500'
  abr = os.environ.get('AUDIO_BITRATE') or '192'
  options['video_bitrate_kbps'] = int(vbr)
  options['audio_bitrate_kbps'] = int(abr)
elif os.environ.get('VIDEO_BITRATE') or os.environ.get('AUDIO_BITRATE'):
  options['reencode'] = True
  if os.environ.get('VIDEO_BITRATE'):
    options['video_bitrate_kbps'] = int(os.environ['VIDEO_BITRATE'])
  if os.environ.get('AUDIO_BITRATE'):
    options['audio_bitrate_kbps'] = int(os.environ['AUDIO_BITRATE'])

if options:
  payload['options'] = options

print(json.dumps(payload))
PY
ABS_MP4="$ABS_PATH" STREAM_ID="$STREAM_ID" DYNAMIC_MODE="$DYNAMIC_MODE" SEGMENT_DURATION="$SEGMENT_DURATION" WINDOW_SIZE="$WINDOW_SIZE" EXTRA_WINDOW_SIZE="$EXTRA_WINDOW_SIZE" SEGMENT_PADDING="$SEGMENT_PADDING" SEGMENT_TEMPLATE="$SEGMENT_TEMPLATE" INIT_TEMPLATE="$INIT_TEMPLATE" REENCODE="$REENCODE" VIDEO_BITRATE="$VIDEO_BITRATE" AUDIO_BITRATE="$AUDIO_BITRATE")

echo "Triggering packaging via $BACKEND_URL/api/dash/package"
tmp_resp="$(mktemp)"
http_code=$(curl -sS -o "$tmp_resp" -w "%{http_code}" -H "Content-Type: application/json" -X POST -d "$REQUEST_PAYLOAD" "$BACKEND_URL/api/dash/package") || true
cat "$tmp_resp"
echo
rm -f "$tmp_resp"
if [[ ! "$http_code" =~ ^2 ]]; then
  echo "Packaging request failed with HTTP $http_code" >&2
  exit 1
fi
echo "Packaging completed successfully."
