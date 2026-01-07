# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory# Use an official Python runtime as a parent image
FROM python:3.11-slim-bullseye

# Install system dependencies for FFmpeg, OpenCV, and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libpq-dev \
    gcc \
    python3-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 5000 for the Flask app
EXPOSE 5000

# Metadata/Labels for Podman identification
LABEL maintainer="Forensic Tool Development"
LABEL version="1.0"
WORKDIR /app

# Install system dependencies for OpenCV, ffmpeg, and other libraries
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Default command (can be overridden in compose)
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]