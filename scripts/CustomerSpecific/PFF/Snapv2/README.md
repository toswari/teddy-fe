# Football Snap Detection System

This system analyzes football game videos to detect the moment of snap using computer vision, YOLO object detection, and motion analysis. It tracks both player movement and camera motion to accurately identify snap moments.

## Features

- YOLO-based player detection
- Camera motion compensation using optical flow
- Motion analysis for snap detection
- Automatic GIF generation of snap moments
- Motion analysis graphs
- Dockerized deployment
- REST API interface

## Requirements

- Docker
- NVIDIA GPU (recommended)
- NVIDIA Container Toolkit (for GPU support)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd SnapDetection
```

2. Build the Docker image:
```bash
docker build -t snap-detection .
```

3. Run the container:
```bash
docker run --gpus all -p 3330:3330 snap-detection
```

## API Usage

The system exposes a REST API endpoint at port 3330.

### Detect Snap

**Endpoint:** `POST /detect-snap`

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: 
  - video: Video file (MP4, AVI, or MOV format)

**Response:**
```json
{
    "snap_frame": 123,
    "gif_url": "/output/video_name_snap.gif",
    "graph_url": "/output/video_name_motion.png"
}
```

### View Output Files

**Endpoint:** `GET /output/<filename>`

Use this endpoint to retrieve the generated GIFs and motion analysis graphs.

## Technical Details

The system uses several advanced computer vision techniques:

1. **Player Detection**: Uses YOLOv8 to detect players in each frame
2. **Camera Motion Tracking**: Uses optical flow to track stable points on the field
3. **Motion Analysis**: Combines player movement and camera motion data to identify the snap moment
4. **Snap Detection**: Analyzes motion patterns to find the characteristic pause followed by sudden movement

## Limitations

- Works best with videos taken from elevated sideline positions
- Requires clear visibility of players
- Video quality affects detection accuracy
- Maximum file size: 16MB

## Error Handling

The API returns appropriate error messages for:
- Missing video files
- Invalid file formats
- Processing errors
- File size limitations 
