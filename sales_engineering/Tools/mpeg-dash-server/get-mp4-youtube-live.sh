#!/bin/bash

# Extract YouTube video ID from Skyline Webcams page and download live stream

if [ $# -eq 0 ]; then
    echo "Usage: $0 <skylinewebcams-url> [duration-seconds]"
    echo "Example: $0 https://www.skylinewebcams.com/en/webcam/united-states/michigan/coldwater/coldwater.html 90"
    exit 1
fi

PAGE_URL="$1"
DURATION="${2:-90}"
OUTPUT_DIR="media"
OUTPUT_FILE="${OUTPUT_DIR}/youtube-live-$(date +%Y%m%d-%H%M%S).mp4"

mkdir -p "$OUTPUT_DIR"

echo "Extracting YouTube video ID from: $PAGE_URL"
VIDEO_ID=$(curl -s "$PAGE_URL" | grep -oE 'youtube\.com/embed/[^"?]+|youtu\.be/[^"?]+' | head -1 | sed -E 's|.*/(embed/)?||')

if [ -z "$VIDEO_ID" ]; then
    echo "❌ Could not find YouTube video ID on the page"
    exit 1
fi

YOUTUBE_URL="https://www.youtube.com/watch?v=${VIDEO_ID}"
echo "Found YouTube video: $YOUTUBE_URL"
echo "Duration: ${DURATION} seconds"
echo "Output: $OUTPUT_FILE"
echo ""

# Check if yt-dlp is installed
if ! command -v yt-dlp &> /dev/null; then
    echo "❌ yt-dlp not found. Install with: brew install yt-dlp"
    exit 1
fi

echo "Starting download..."

# Get the stream URL from yt-dlp and pipe to ffmpeg directly for accurate duration control
STREAM_URL=$(yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" -g "$YOUTUBE_URL" | head -1)

if [ -z "$STREAM_URL" ]; then
    echo "❌ Could not extract stream URL"
    exit 1
fi

# Use ffmpeg directly with the stream URL for precise time control
ffmpeg -i "$STREAM_URL" \
  -t "$DURATION" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Download complete: $OUTPUT_FILE"
    echo "File size: $(du -h "$OUTPUT_FILE" | cut -f1)"
else
    echo ""
    echo "❌ Download failed (exit code: $?)"
    exit 1
fi
