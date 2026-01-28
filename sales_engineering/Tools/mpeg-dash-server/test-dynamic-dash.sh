#!/bin/bash

# Test dynamic/live DASH manifest generation

set -e

echo "=== Testing Dynamic MPEG-DASH Manifest Generation ==="
echo ""

# Find first MP4 file
MP4_FILE=$(find media -name "*.mp4" -type f | head -1)
if [ -z "$MP4_FILE" ]; then
    echo "❌ No MP4 file found in media/ directory"
    exit 1
fi

echo "📹 Source file: $MP4_FILE"
echo ""

# Create test output directory
TEST_OUTPUT="media/dash/test-dynamic-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$TEST_OUTPUT"

echo "🔧 Generating dynamic DASH manifest..."
echo "   - Mode: dynamic"
echo "   - Segment duration: 4s"
echo "   - Window size: 6 segments"
echo "   - Update period: 8s"
echo "   - Time-shift buffer: 3600s (1 hour)"
echo ""

ffmpeg -y -i "$MP4_FILE" \
  -map 0:v -map 0:a? \
  -c:v copy -c:a copy \
  -f dash \
  -use_template 1 \
  -use_timeline 1 \
  -init_seg_name "init-stream\$RepresentationID\$.m4s" \
  -media_seg_name "chunk-stream\$RepresentationID\$-\$Number%05d\$.m4s" \
  -streaming 1 \
  -ldash 1 \
  -seg_duration 4.0 \
  -window_size 6 \
  -extra_window_size 6 \
  -update_period 8 \
  "$TEST_OUTPUT/manifest.mpd"

if [ $? -eq 0 ] && [ -f "$TEST_OUTPUT/manifest.mpd" ]; then
    echo "✅ Dynamic manifest generated successfully"
    echo ""
    echo "=== Manifest Analysis ==="
    
    # Extract key attributes
    TYPE=$(xmllint --xpath 'string(//*[local-name()="MPD"]/@type)' "$TEST_OUTPUT/manifest.mpd" 2>/dev/null)
    PROFILE=$(xmllint --xpath 'string(//*[local-name()="MPD"]/@profiles)' "$TEST_OUTPUT/manifest.mpd" 2>/dev/null)
    MIN_UPDATE=$(xmllint --xpath 'string(//*[local-name()="MPD"]/@minimumUpdatePeriod)' "$TEST_OUTPUT/manifest.mpd" 2>/dev/null)
    DELAY=$(xmllint --xpath 'string(//*[local-name()="MPD"]/@suggestedPresentationDelay)' "$TEST_OUTPUT/manifest.mpd" 2>/dev/null)
    TIME_SHIFT=$(xmllint --xpath 'string(//*[local-name()="MPD"]/@timeShiftBufferDepth)' "$TEST_OUTPUT/manifest.mpd" 2>/dev/null)
    AVAIL_START=$(xmllint --xpath 'string(//*[local-name()="MPD"]/@availabilityStartTime)' "$TEST_OUTPUT/manifest.mpd" 2>/dev/null)
    
    echo "Type: $TYPE"
    echo "Profile: $PROFILE"
    echo "Minimum Update Period: $MIN_UPDATE"
    echo "Suggested Presentation Delay: $DELAY"
    echo "Time-Shift Buffer Depth: $TIME_SHIFT"
    echo "Availability Start Time: $AVAIL_START"
    echo ""
    
    if [ "$TYPE" = "dynamic" ]; then
        echo "✅ Manifest type is 'dynamic' (live streaming)"
    else
        echo "❌ Manifest type is '$TYPE' (expected 'dynamic')"
    fi
    
    if [ -n "$AVAIL_START" ]; then
        echo "✅ availabilityStartTime present (required for live)"
    else
        echo "❌ availabilityStartTime missing"
    fi
    
    echo ""
    echo "📄 Full manifest preview (first 30 lines):"
    head -30 "$TEST_OUTPUT/manifest.mpd"
    echo ""
    echo "📁 Output directory: $TEST_OUTPUT"
    echo "📊 Total files: $(ls -1 "$TEST_OUTPUT" | wc -l | xargs)"
    
else
    echo "❌ Failed to generate dynamic manifest"
    exit 1
fi
