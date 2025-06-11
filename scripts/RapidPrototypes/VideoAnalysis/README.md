# Video Analysis

Video analysis platform that uses Clarifai's AI models to analyze equestrian videos and provide detailed insights about rider performance, horse behavior, and event analysis.

## Features

- **Video Analysis**
  - Stream video processing with live progress updates
  - Frame-by-frame analysis with detailed insights
  - Support for various equestrian events (dressage, show jumping, etc.)

- **Interactive Chat Interface**
  - Ask questions about the analyzed video
  - Get detailed explanations of events and behaviors
  - Toggle between raw and processed responses
  - "RAG" needs to be rebuilt to use embeddings rather than longer contexts with each step

- **Customizable Analysis**
  - Select from predefined event categories
  - Add custom analysis prompts
  - Adjust analysis parameters


# Docker Deployment

Docker Compose Option: 
```bash
docker-compose up --build -d
```

Regular Docker Image:
1. Build the Docker image:
```bash
docker build -t video-analysis-platform .
```

2. Run the container:
```bash
docker run -p 5000:5000 video-analysis-platform
```

## Project Structure

```
video-analysis-platform/
├── app.py                 # Main Flask application
├── frame_analyzer.py      # Video frame analysis logic
├── rag_engine.py         # RAG-based question answering
├── prompts_config.py     # Analysis prompts configuration
├── model_configs.json    # AI model configurations
├── requirements.txt      # Python dependencies
├── static/              # Static files (CSS, JS, images)
├── templates/           # HTML templates
└── uploads/            # Temporary video storage
```

## API Endpoints

- `POST /analyze` - Upload and analyze video
- `POST /analyze/stream` - Stream video analysis
- `POST /chat` - Send chat message
- `GET /chat/stream/<question>` - Stream chat response
