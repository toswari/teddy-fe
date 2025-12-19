# Visual Inspection Demo

## Computer Vision in Visual Inspection:
• Automated inspection ensuring 24/7 consistency and accuracy  
• Real-time defect detection reducing production losses  
• Scalable solution for high-volume inspection needs  
• Data-driven insights for process improvement

## Overview
This is a Streamlit application demonstrating four visual inspection use cases using computer vision models trained on the Clarifai Platform:

1. **Sheet Metal Defect Classification**
   - Detects defects in metal surfaces
   - Classification with confidence scores

2. **Electrical Insulator Defect Detection**
   - Identifies defects in electrical insulators
   - Provides bounding boxes and confidence scores

3. **Surface Crack Segmentation**
   - Segments and highlights cracks in surfaces
   - Real-time crack region visualization



## Setup

### Prerequisites
- Python 3.8 or higher (for local setup)
- Docker (for containerized setup)
- Clarifai PAT (Personal Access Token) - Add to `.streamlit/secrets.toml`

### Option A: Docker Setup (Recommended)

#### Quick Start with Docker
```bash
# 1. Create secrets file (required before building)
mkdir -p .streamlit
echo 'CLARIFAI_PAT = "your-clarifai-pat-here"' > .streamlit/secrets.toml

# 2. Build and run container
chmod +x create-docker.sh
./create-docker.sh
```

The script will automatically:
- Build the Docker image with your secrets and configuration
- Stop any existing containers
- Start the application on port 8520

Access the application at `http://localhost:8520`

**Note:** The secrets.toml file is copied into the Docker image during build. If you update your secrets, you need to rebuild the image using `./create-docker.sh` again.

#### Docker Management Commands
```bash
# View logs
docker logs visual-inspection-app -f

# Stop container
docker stop visual-inspection-app

# Start existing container
docker start visual-inspection-app

# Remove container
docker rm -f visual-inspection-app

# Remove image
docker rmi visual-inspection-demo
```

### Option B: Local Setup

#### Installation
```bash
# Install dependencies
pip install -r requirements.txt
```

#### Running Locally

**Method 1: Using scripts (Recommended)**
```bash
# Make scripts executable (first time only)
chmod +x start.sh stop.sh

# Start the application (default port 8520)
./start.sh

# Or specify a custom port
./start.sh 8502

# Stop the application
./stop.sh
```

**Method 2: Manual start**
```bash
streamlit run app.py --server.port=8520
```

The application will be available at `http://localhost:8520`

## Configuration
- Customize via sidebar controls
- Adjustable thresholds and display options
- Configurable image sources
- Visual theme customization

## Models
All models used are custom-trained using the Clarifai platform and tailored to each specific use case. The Clarifai platform simplifies the entire process of creating and training AI models, making it both easy and efficient. With just a single click, your model is not only trained but also automatically deployed, ready to enhance your business solutions instantly.

- Surface Defect Detection (surface-defects)
- Insulator Detection (insulator-condition-inception)
- Crack Segmentation (crack-segmentation)