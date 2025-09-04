FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsm6 libxext6 libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

## Removed YOLO model download (Clarifai-based pipeline)

# Create necessary directories
RUN mkdir -p outputs sample_videos

# Copy sample videos
COPY sample_videos/ sample_videos/

# Copy the rest of the application
COPY . .

# Default command to show usage
CMD ["python3", "main.py", "--help"] 