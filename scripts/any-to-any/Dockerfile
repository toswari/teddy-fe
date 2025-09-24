FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime   

## Install system dependencies for video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    wget \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make the startup script executable
RUN chmod +x start_runner.sh

# Expose port for the runner
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app

# Command to run the Clarifai local runner
CMD ["./start_runner.sh"]