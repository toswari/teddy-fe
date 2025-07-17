# Video Processor Clarifai Runner

A Clarifai local runner that processes video files using ffmpeg and uploads results to S3. This containerized model provides three endpoints for video processing with simplified, secure input handling.

## Features

- **Video Processing Pipeline**: Downloads videos from URLs, extracts metadata using ffmpeg, uploads to S3
- **Comprehensive Metadata**: Duration, resolution, FPS, codecs, bitrates, file size, creation time, and stream information
- **Multiple Endpoints**: `predict`, `generate`, and `s` - all perform the same video processing
- **Secure Credential Management**: AWS credentials loaded from environment variables
- **Simplified Input**: Only requires video URL and optional output prefix
- **Docker Deployment**: Fully containerized with Clarifai local runner integration

## Setup

### Prerequisites

- Docker and Docker Compose
- Clarifai account and Personal Access Token (PAT)
- AWS credentials for S3 upload

### Environment Variables

Configure your `.env` file with the following variables:

```bash
# Clarifai Configuration
CLARIFAI_PAT=your_clarifai_personal_access_token_here
CLARIFAI_USER_ID=your_clarifai_user_id

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_DEFAULT_REGION=us-east-1
DEFAULT_S3_BUCKET=your-default-bucket-name

# Optional
LOG_LEVEL=INFO
```

### Build and Deploy

1. **Build and start the container**:
```bash
docker-compose up --build -d
```

2. **Check the logs**:
```bash
docker logs clarifai-video-processor
```

The Clarifai local runner will automatically:
- Create compute cluster and nodepool if needed
- Deploy the model to the cluster
- Start accepting requests

## Usage

### Input Format

All endpoints accept a simple JSON input with AWS credentials loaded from environment:

```json
{
  "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
  "output_prefix": "my_videos/"
}
```

### Available Endpoints

All three endpoints perform the same video processing but with different interfaces:

1. **predict**: Standard prediction endpoint
2. **generate**: Streaming/generator endpoint (yields single result)
3. **s**: Stream processing endpoint for batch operations

### Example API Calls

```python
from clarifai.client import Model

model = Model("https://clarifai.com/your-user/local-runner-app/models/local-runner-model",
              deployment_id='local-runner-deployment')

# Process a video
result = model.predict(
    prompt='{"video_url": "https://example.com/video.mp4", "output_prefix": "processed/"}',
    process_type="full"
)

# Stream processing
for result in model.generate(
    prompt='{"video_url": "https://example.com/video.mp4"}',
    iterations=1
):
    print(result)
```

### Output Format

All endpoints return the same structured response:

```json
{
  "endpoint": "predict",
  "status": "success",
  "video_url": "https://bucket.s3.region.amazonaws.com/processed/video.mp4",
  "metadata_url": "https://bucket.s3.region.amazonaws.com/processed/video_metadata.json",
  "metadata": {
    "filename": "video.mp4",
    "duration": 596.47,
    "width": 1280,
    "height": 720,
    "fps": 24.0,
    "bitrate": 2119234,
    "format": "mov,mp4,m4a,3gp,3g2,mj2",
    "codec": "h264",
    "audio_codec": "aac",
    "audio_bitrate": 125587,
    "audio_sample_rate": 44100,
    "audio_channels": 2,
    "file_size": 158008374,
    "creation_time": "2010-01-10T08:29:06.000000Z",
    "processed_at": "2025-07-17T15:00:23.613656",
    "streams": [...]
  },
  "processing_time": "2025-07-17T15:00:23.613656"
}
```

## Architecture

### Project Structure

```
runner_videofile/
├── 1/
│   └── model.py          # Main model implementation
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Service orchestration
├── requirements.txt      # Python dependencies
├── start_runner.sh       # Container startup script
├── .env                  # Environment variables (not in repo)
└── README.md            # This file
```

### Key Components

- **Model Class**: Implements Clarifai `ModelClass` with three endpoints
- **Video Processing**: Downloads, analyzes with ffmpeg, uploads to S3
- **Environment Integration**: Secure credential management
- **Docker Container**: Includes ffmpeg and Python dependencies
- **Clarifai Integration**: Automatic runner deployment and management

## Error Handling

The model includes comprehensive error handling with helpful examples:

```json
{
  "endpoint": "predict",
  "status": "error",
  "message": "Invalid JSON input. Please provide a valid JSON string.",
  "example": {
    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "output_prefix": "my_videos/"
  },
  "note": "AWS credentials are loaded from environment variables"
}
```

## Security

- **No credentials in requests**: AWS credentials are loaded from environment variables
- **Container isolation**: All processing happens in isolated Docker container
- **Minimal attack surface**: Only video URL and output prefix are user-provided
- **Secure defaults**: Fallback values for missing environment variables

## Development

### Local Testing

Test the model locally:
```bash
cd 1
python model.py
```

### Container Development

Build and test the container:
```bash
docker-compose build
docker-compose up --build
```

### Adding Features

The model is structured for easy extension:
- Add new endpoints by decorating methods with `@ModelClass.method`
- Modify video processing in the `process_video` function
- Update environment variables in `.env` file

## Troubleshooting

1. **Container won't start**: Check `.env` file has correct CLARIFAI_PAT and CLARIFAI_USER_ID
2. **S3 upload fails**: Verify AWS credentials and bucket permissions
3. **Video download fails**: Check network connectivity and video URL validity
4. **Processing errors**: Check container logs with `docker logs clarifai-video-processor`

## Support

For issues with:
- **Clarifai platform**: Check [Clarifai documentation](https://docs.clarifai.com)
- **Video processing**: Verify ffmpeg compatibility with your video format
- **AWS S3**: Check bucket permissions and region settings
