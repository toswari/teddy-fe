# Video Analysis

Video analysis platform that uses Clarifai's AI models to analyze videos across multiple domains and provide detailed insights about events, behaviors, and objects in the video.

## Features

- **Advanced Fish Analysis** 🐠 (Primary Feature)
  - Real-time fish species identification and counting
  - Configurable processing rate (0.5 - 5 FPS)
  - Separate confidence scores for fish detection and image quality
  - Detailed metrics per detected fish:
    - Species identification
    - Count tracking with timestamps
    - Location mapping in frame
    - Size estimation
    - Behavior analysis
  - Comprehensive image quality assessment:
    - Overall quality rating
    - Sharpness/blur detection
    - Lighting condition analysis
    - Water clarity evaluation
    - Visibility issue identification
  - Fish detection alerts (only when fish count > 0)

- **Multi-Domain Video Analysis**
  - Stream video processing with live progress updates
  - Frame-by-frame analysis with detailed insights
  - Support for 15+ analysis categories:
    - **Marine Biology**: Fish Analysis (Default)
    - **Sports**: Bronc Riding, Bull Riding, Barrel Racing, Sheep Riding, Football, Basketball, Soccer, Baseball, Hockey
    - **Surveillance**: Military/Surveillance, Public Safety, Security/Shoplifting
    - **Industrial**: Flare Safety
    - **General**: Content rating and categorization

- **Legacy Fish Analysis Documentation** 🐟
  - Identifies fish species by name (e.g., Clownfish, Bluefin Tuna, Goldfish)
  - Counts individual fish at each second of the video
  - Tracks fish locations and movements
  - Analyzes fish sizes and behaviors (swimming, feeding, schooling)
  - Assesses environmental context (coral reef, open water, aquarium)
  - **Image Quality Assessment**:
    - Overall quality rating
    - Sharpness detection (blur analysis)
    - Lighting conditions (well-lit, dim, overexposed, underexposed)
    - Water clarity evaluation
    - Visibility issues identification (glare, reflections, particles)

- **Interactive Chat Interface**
  - Ask questions about the analyzed video
  - Get detailed explanations of events and behaviors
  - Toggle between raw and processed responses
  - Model thinking visibility option
  - "RAG" needs to be rebuilt to use embeddings rather than longer contexts with each step

- **Customizable Analysis**
  - Select from 14+ predefined analysis categories
  - Add custom analysis prompts
  - Adjust analysis parameters
  - Real-time progress tracking


## Usage

### Quick Start with start.sh

1. **Configure Credentials (One-time setup)**
   
   Create a `.env` file or copy from the example:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Clarifai credentials:
   ```env
   CLARIFAI_USERNAME=your_username_here
   CLARIFAI_PAT=your_personal_access_token_here
   ```
   
   Get your credentials from: https://clarifai.com/settings/security

2. **Start the Application**
   ```bash
   ./start.sh
   ```
   
   The script will automatically:
   - Check Python installation
   - Set up virtual environment (if needed)
   - Install dependencies
   - Load credentials from .env
   - Create necessary directories
   - Start the Flask application
   
   Access at `http://localhost:5000`

### Conda Environment Setup (Recommended)

For a clean, isolated environment using conda:

1. **Run the setup script**
   ```bash
   ./setup-conda-env.sh
   ```
   
   This will:
   - Create a conda environment named `VideoAnalysis-311` with Python 3.11
   - Install all required dependencies from requirements.txt
   - Handle existing environment conflicts

2. **Activate the environment**
   ```bash
   conda activate VideoAnalysis-311
   ```

3. **Start the application**
   ```bash
   python app.py
   ```
   
   Access at `http://localhost:5000`

### Manual Start (Alternative)

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the Application**
   ```bash
   python app.py
   ```
   Access at `http://localhost:5000`

3. **Enter Credentials**
   - Username: Your Clarifai username
   - Personal Access Token (PAT): Your Clarifai API token

### Using the Application

1. **Select Analysis Category**
   - **Default**: Fish Analysis (optimized for marine life detection)
   - Choose from 15+ categories for different analysis types
   - Or select "General Analysis" for automatic categorization

2. **Select Processing Rate (FPS)**
   - **0.5 FPS**: 1 frame every 2 seconds (Fastest)
   - **1 FPS**: 1 frame per second (Recommended, Default)
   - **2 FPS**: 2 frames per second (Detailed)
   - **3 FPS**: 3 frames per second (Very Detailed)
   - **5 FPS**: 5 frames per second (Maximum Detail)
   - Higher FPS = more frames analyzed = longer processing time

3. **Upload Video**
   - Supported formats: MP4, AVI, MOV, etc.
   - Maximum file size: 200MB
   - Video will be analyzed at your selected FPS rate

3. **View Results**
   - Real-time progress updates
   - Frame-by-frame analysis with timestamps
   - Interactive video playback with frame markers
   - Comprehensive summary report

4. **Ask Questions (Chat Feature)**
   - Click "Ask about Results" button
   - Ask questions about analyzed content
   - Toggle "Show model thinking" for detailed reasoning

## Fish Analysis Example Output

```json
{
    "category": "fish analysis",
    "fish_species": ["Clownfish", "Blue Tang"],
    "total_count": 5,
    "fish_details": [
        {
            "species": "Clownfish",
            "count": 3,
            "locations": ["near coral", "bottom right"],
            "sizes": ["small", "small", "medium"],
            "behavior": "swimming near anemone",
            "confidence": 0.92
        },
        {
            "species": "Blue Tang",
            "count": 2,
            "locations": ["center", "top left"],
            "sizes": ["medium", "medium"],
            "behavior": "schooling",
            "confidence": 0.88
        }
    ],
    "environment": "coral reef aquarium",
    "image_quality": {
        "overall": "good",
        "sharpness": "sharp",
        "lighting": "well-lit",
        "water_clarity": "clear",
        "visibility_issues": ["slight glare on glass"],
        "confidence": 0.95
    },
    "reasoning": "Clear visibility with good lighting allows accurate fish count and identification"
}
```

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
- `POST /analyze/stream` - Stream video analysis with real-time updates
- `POST /chat` - Send chat message about analysis results
- `GET /chat/stream/<question>` - Stream chat response

## Technology Stack

For detailed information about the technology stack, pros/cons, and architecture decisions, see [TechnologyStack.md](TechnologyStack.md).

**Key Technologies:**
- **Backend**: Python 3.11, Flask 2.3.3
- **AI/ML**: Clarifai Platform (SDK, gRPC)
- **Computer Vision**: OpenCV 4.11, MoviePy, FFmpeg
- **Frontend**: Tailwind CSS, Socket.IO, HTML5/JavaScript
- **Deployment**: Docker, Docker Compose

## Analysis Categories

| Category | Description |
|----------|-------------|
| **General Analysis** | Automatic content categorization and rating |
| **Bronc Riding** | Rider performance, horse behavior, safety analysis |
| **Bull Riding** | Rider performance, bull behavior, scoring |
| **Barrel Racing** | Racing performance, barrel positions, timing |
| **Sheep Riding** | Mutton busting performance and safety |
| **Football** | Play types, field position, player tracking |
| **Basketball** | Play analysis, ball possession, player positioning |
| **Soccer** | Attack/defense patterns, ball location, field position |
| **Baseball** | Pitch analysis, batting, fielding, base positions |
| **Hockey** | Puck location, zone analysis, play types |
| **Military/Surveillance** | Object detection, threat assessment |
| **Public Safety** | Safety monitoring, danger detection |
| **Flare Safety** | Industrial stack safety, flare monitoring |
| **Security/Shoplifting** | Suspicious behavior detection, theft prevention |
| **Fish Analysis** 🐠 | Species ID, counting, behavior, image quality |

## SAMPLE VIDEOS FOR DEMO
- https://drive.google.com/drive/folders/1kXfpolSCYhHG55W72wSbqTTQrJ7sF1zi?usp=drive_link

## Recent Updates (Marine Branch)

### Fish Analysis Feature 🐠 (Now Default)
- **Set as Default Category**: Fish Analysis is now the primary use case
- **Species Identification**: Recognizes specific fish species with individual confidence scores
- **Fish Counting**: Accurate count of individual fish per frame
- **Location Tracking**: Identifies where fish are positioned in the frame
- **Behavior Analysis**: Describes fish activities (swimming, feeding, schooling)
- **Environmental Context**: Identifies habitat and water conditions
- **Separate Confidence Scores**: 
  - Fish detection confidence per species
  - Image quality assessment confidence
- **Image Quality Assessment**: 
  - Overall quality rating
  - Sharpness/blur detection
  - Lighting condition analysis
  - Water clarity evaluation
  - Visibility issue identification
- **Smart Alerts**: Fish detection notifications only when fish count > 0

### Processing Enhancements
- **Configurable FPS Selection**: Choose processing rate from 0.5 to 5 FPS
- **Optimized for Marine Videos**: Default settings tuned for underwater footage

### Environment Configuration
- **Credentials Pre-population**: Username and PAT loaded from .env file
- **Conda Environment Support**: Integrated with VideoAnalysis-312 conda environment
- **Startup Script**: Enhanced start.sh with automatic environment detection

### Added Documentation
- **TechnologyStack.md**: Comprehensive documentation of all technologies used, including pros/cons and architectural decisions
- **Enhanced README**: Updated with Fish Analysis focus and new features

## Contributing

When adding new analysis categories:
1. Add prompt to `prompts_config.py` with JSON output format
2. Add option to category dropdown in `templates/index.html`
3. Update README.md with category description
4. Test with sample videos

## License

Copyright © 2024 Clarifai, Inc. All rights reserved.

## Support

For issues or questions, please contact the development team or create an issue in the repository.
