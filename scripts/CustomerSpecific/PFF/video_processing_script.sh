#!/bin/bash

set -e

process_video() {
    local MP4_FILE="$1"
    
    if [[ ! -f "$MP4_FILE" ]]; then
        echo "File not found: $MP4_FILE"
        return 1
    fi
    
    MP4_FILE=$(realpath "$MP4_FILE")
    
    VIDEO_NAME=$(basename "$MP4_FILE" .mp4)
    OUTPUT_BASE_DIR="cyu_outputs/$VIDEO_NAME"
    FRAMES_DIR="$OUTPUT_BASE_DIR/frames"
    INFERENCE_OUT_DIR="$OUTPUT_BASE_DIR/inference"
    
    mkdir -p "$FRAMES_DIR"
    mkdir -p "$INFERENCE_OUT_DIR"
    
    # Extract frames
    ffmpeg -i "$MP4_FILE" -q:v 1 "$FRAMES_DIR/%04d.jpg" -y
    
    # Run inference
    python deploy/video-detect-track/example_inference.py "$MP4_FILE" \
        --output_formats pb mp4 \
        --out_dir "$INFERENCE_OUT_DIR"
    
    # Run recognition
    DETECTION_FILE="$INFERENCE_OUT_DIR/${VIDEO_NAME}_det.pb"
    
    python scripts/recognize_player_id.py "$DETECTION_FILE" "$FRAMES_DIR"
}

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 video1.mp4 [video2.mp4 ...]"
    exit 1
fi

for mp4_file in "$@"; do
    process_video "$mp4_file"
done