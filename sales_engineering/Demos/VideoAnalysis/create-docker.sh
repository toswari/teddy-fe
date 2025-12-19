#!/bin/bash

# Script to build and run VideoAnalysis Docker container
# This script creates a Docker image and runs it as a container

set -e  # Exit on error

IMAGE_NAME="video-analysis-platform"
CONTAINER_NAME="video-analysis-app"
PORT="5001"
ENV_FILE=".env"

echo "=========================================="
echo "VideoAnalysis Docker Build & Run Script"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: .env file not found"
    echo "Creating .env from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Please edit .env and add your Clarifai credentials before continuing."
        read -p "Press Enter when ready to continue..."
    else
        echo "Error: .env.example not found"
        echo "Please create a .env file with CLARIFAI_USERNAME and CLARIFAI_PAT"
        exit 1
    fi
fi

# Check if container is already running
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' already exists."
    read -p "Do you want to stop and remove it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping and removing existing container..."
        docker stop ${CONTAINER_NAME} 2>/dev/null || true
        docker rm ${CONTAINER_NAME} 2>/dev/null || true
    else
        echo "Exiting without changes."
        exit 0
    fi
fi

# Check if image exists and ask to rebuild
if docker images --format '{{.Repository}}' | grep -q "^${IMAGE_NAME}$"; then
    echo "Image '${IMAGE_NAME}' already exists."
    read -p "Do you want to rebuild it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Rebuilding Docker image..."
        docker build -t ${IMAGE_NAME} .
    else
        echo "Using existing image..."
    fi
else
    echo "Building Docker image: ${IMAGE_NAME}..."
    docker build -t ${IMAGE_NAME} .
fi

echo ""
echo "Starting Docker container: ${CONTAINER_NAME}..."

# Run the container with environment variables from .env file
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:${PORT} \
    --env-file ${ENV_FILE} \
    -v "$(pwd)/uploads:/app/uploads" \
    --restart unless-stopped \
    ${IMAGE_NAME}

echo ""
echo "=========================================="
echo "Container Started Successfully!"
echo "=========================================="
echo ""
echo "Container Name: ${CONTAINER_NAME}"
echo "Access the application at: http://localhost:${PORT}"
echo ""
echo "Useful commands:"
echo "  View logs:        docker logs ${CONTAINER_NAME}"
echo "  Follow logs:      docker logs -f ${CONTAINER_NAME}"
echo "  Stop container:   docker stop ${CONTAINER_NAME}"
echo "  Start container:  docker start ${CONTAINER_NAME}"
echo "  Remove container: docker rm ${CONTAINER_NAME}"
echo "  Remove image:     docker rmi ${IMAGE_NAME}"
echo ""
