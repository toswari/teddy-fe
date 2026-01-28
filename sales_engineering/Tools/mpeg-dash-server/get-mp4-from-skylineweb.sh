#!/bin/bash

# Capture live HLS stream from Skyline Webcams and convert to MP4

URL="https://hd-auth.skylinewebcams.com/live.m3u8?a=86e11cp23tspnr0hnvsgfasva4"
DURATION=90
OUTPUT="media/skylineweb-$(date +%Y%m%d-%H%M%S).mp4"

echo "Starting capture from Skyline Webcams..."
echo "URL: $URL"
echo "Duration: ${DURATION} seconds"
echo "Output: $OUTPUT"
echo ""

ffmpeg -i "$URL" \
  -t "$DURATION" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  "$OUTPUT"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Capture complete: $OUTPUT"
    echo "File size: $(du -h "$OUTPUT" | cut -f1)"
else
    echo ""
    echo "❌ Capture failed (exit code: $?)"
    exit 1
fi
