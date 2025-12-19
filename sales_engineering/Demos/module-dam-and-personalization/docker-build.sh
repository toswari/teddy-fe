#!/usr/bin/env bash
set -euo pipefail

# Docker build and run script for Clarifai DAM Demo

IMAGE_NAME="clarifai-dam-demo"
CONTAINER_NAME="clarifai-dam-demo"
PORT="${PORT:-8501}"

echo "Building Docker image: ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}:latest" .

echo ""
echo "Stopping any existing container..."
docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm "${CONTAINER_NAME}" 2>/dev/null || true

echo ""
echo "Starting container: ${CONTAINER_NAME}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:8501" \
  -v "$(pwd)/.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro" \
  "${IMAGE_NAME}:latest"

echo ""
echo "✅ Container started successfully!"
echo "📍 Access the app at: http://localhost:${PORT}"
echo ""
echo "Useful commands:"
echo "  View logs:    docker logs -f ${CONTAINER_NAME}"
echo "  Stop:         docker stop ${CONTAINER_NAME}"
echo "  Restart:      docker restart ${CONTAINER_NAME}"
echo "  Remove:       docker rm -f ${CONTAINER_NAME}"
