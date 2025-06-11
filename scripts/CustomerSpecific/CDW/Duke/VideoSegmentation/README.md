# Basketball Video Segmenter

A web application that allows users to upload basketball game videos and automatically extract clips showing players on the court (gameplay), excluding commercials, fan close-ups, or other non-gameplay footage.

## Features

- Upload basketball videos (MP4, AVI, MOV formats supported)
- Process videos using a machine learning model to identify gameplay segments
- Extract clips containing gameplay only
- Display extracted clips with thumbnails
- Play original video or individual clips
- Download individual clips
- Real-time processing progress updates

## Requirements

- Python 3.8+
- Flask
- OpenCV
- PyTorch
- NumPy
- PIL
- Flask-SocketIO

## Usage

1. Click "Select Video" to choose a basketball game video file.
2. Click "Upload & Process" to start processing the video.
3. Wait for the processing to complete (you can track the progress with the progress bar).
4. Once processing is complete:
   - The original video will appear in the video player.
   - Below the player, you'll see thumbnails of all extracted gameplay clips.
   - Click on any thumbnail or the "Play" button to view a specific clip.
   - Use the "Download" button to save any clip to your computer.

## Configuration

The application uses a configuration file (`config.json`) that contains:

- Class names for video classification
- Target class to extract (gameplay)
- Model configuration
- Video processing parameters

You can modify these settings to adjust the behavior of the application.

## Technical Details

- **Backend**: Flask with Flask-SocketIO for real-time progress updates
- **Frontend**: HTML, JavaScript, Tailwind CSS
- **Video Processing**: OpenCV/FFMPEG for frame extraction and clip generation
- **Machine Learning**: PyTorch models for frame classification

## Project Structure

```
project/
├── app.py                  # Flask application (main backend)
├── config.json             # Main configuration file
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── Dockerfile              # Docker support
├── docker-compose.yml      # Docker Compose support
├── model/                  # Model directory
│   ├── player_detector.pt >> Found here: https://drive.google.com/drive/folders/1xd-wv_zSMNGr9qze8AvTljz-f4OKk8oq
│   └── court_keypoint_detector.pt >> Found here: https://drive.google.com/drive/folders/1xd-wv_zSMNGr9qze8AvTljz-f4OKk8oq
├── static/                 # Static files
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   ├── logo/
│   │   └── logo.png
│   └── uploads/            # Uploaded videos and generated clips
│       ├── ...             # .mp4 and .jpg files
├── templates/              # HTML templates
│   └── index.html          # Main UI page
└── .gitignore              # Git ignore file
```

## Limitations

- Maximum upload file size: 2GB [In Development]
- Processing time depends on video length and resolution
- For very long videos, processing may take several minutes

