#!/bin/bash

set -e

# Get script directory and change to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
cd "$PROJECT_ROOT"

# Default values
RUN_FULL_PIPELINE=true
RECOGNITION_ONLY=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] video1.mp4 [video2.mp4 ...]"
    echo "Options:"
    echo "  --recognition-only    Run only player recognition (assumes detection outputs exist)"
    echo "  --full-pipeline      Run full pipeline from video to recognition (default)"
    echo "  -h, --help           Show this help message"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --recognition-only)
            RECOGNITION_ONLY=true
            RUN_FULL_PIPELINE=false
            shift
            ;;
        --full-pipeline)
            RUN_FULL_PIPELINE=true
            RECOGNITION_ONLY=false
            shift
            ;;
        -h|--help)
            show_usage
            ;;
        *.mp4)
            break
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

process_video_full() {
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
    
    echo "Processing video: $MP4_FILE"
    echo "Output directory: $OUTPUT_BASE_DIR"
    
    # Extract frames
    echo "Extracting frames..."
    ffmpeg -i "$MP4_FILE" -q:v 1 "$FRAMES_DIR/%04d.jpg" -y
    
    # Run inference
    echo "Running detection and tracking..."
    python deploy/video-detect-track/example_inference.py "$MP4_FILE" \
        --output_formats pb mp4 \
        --out_dir "$INFERENCE_OUT_DIR"
    
    # Run recognition
    DETECTION_FILE="$INFERENCE_OUT_DIR/${VIDEO_NAME}_det.pb"
    
    echo "Running player ID recognition..."
    python scripts/PlayerID/recognize_player_id.py "$DETECTION_FILE" "$FRAMES_DIR"
    
    echo "Completed processing: $MP4_FILE"
}

process_recognition_only() {
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
    DETECTION_FILE="$INFERENCE_OUT_DIR/${VIDEO_NAME}_det.pb"
    
    # Check if required inputs exist
    if [[ ! -d "$FRAMES_DIR" ]]; then
        echo "Error: Frames directory not found: $FRAMES_DIR"
        echo "Run with --full-pipeline first to generate frames and detections"
        return 1
    fi
    
    if [[ ! -f "$DETECTION_FILE" ]]; then
        echo "Error: Detection file not found: $DETECTION_FILE"
        echo "Run with --full-pipeline first to generate detections"
        return 1
    fi
    
    echo "Running player ID recognition only for: $MP4_FILE"
    echo "Using existing frames: $FRAMES_DIR"
    echo "Using existing detections: $DETECTION_FILE"
    
    # Run recognition
    python scripts/PlayerID/recognize_player_id.py "$DETECTION_FILE" "$FRAMES_DIR"
    
    echo "Completed recognition for: $MP4_FILE"
}

if [[ $# -eq 0 ]]; then
    show_usage
fi

for mp4_file in "$@"; do
    if [[ "$RECOGNITION_ONLY" == true ]]; then
        process_recognition_only "$mp4_file"
    else
        process_video_full "$mp4_file"
    fi
done