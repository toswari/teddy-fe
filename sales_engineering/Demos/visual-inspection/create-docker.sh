#!/bin/bash

# Visual Inspection Demo - Docker Container Creation Script
# This script builds and runs the Docker container for the application

set -e  # Exit on error

# Configuration
IMAGE_NAME="visual-inspection-demo"
CONTAINER_NAME="visual-inspection-app"
PORT=8520

echo "🐳 Visual Inspection Demo - Docker Setup"
echo "=========================================="

# Function to check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "❌ Error: Docker is not installed or not in PATH"
        echo "Please install Docker from: https://docs.docker.com/get-docker/"
        exit 1
    fi
    echo "✓ Docker is installed"
}

# Function to check if secrets file exists
check_secrets() {
    if [ ! -f .streamlit/secrets.toml ]; then
        echo "⚠️  Warning: .streamlit/secrets.toml not found"
        echo "The application requires a Clarifai PAT in secrets.toml"
        echo "Creating .streamlit directory..."
        mkdir -p .streamlit
        echo "Please create .streamlit/secrets.toml with:"
        echo '  CLARIFAI_PAT = "your-clarifai-pat-here"'
        read -p "Press Enter to continue after creating the secrets file, or Ctrl+C to exit..."
    fi
    echo "✓ Secrets file found"
}

# Function to stop existing container
stop_existing() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "🛑 Stopping existing container..."
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
        docker rm "$CONTAINER_NAME" 2>/dev/null || true
        echo "✓ Existing container removed"
    fi
}

# Function to build Docker image
build_image() {
    echo ""
    echo "🔨 Building Docker image: $IMAGE_NAME"
    echo "This may take a few minutes on first build..."
    docker build -t "$IMAGE_NAME" .
    echo "✓ Docker image built successfully"
}

# Function to run Docker container
run_container() {
    echo ""
    echo "🚀 Starting Docker container: $CONTAINER_NAME"
    
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p "$PORT:8520" \
        --restart unless-stopped \
        "$IMAGE_NAME"
    
    echo "✓ Container started successfully"
}

# Function to show container status
show_status() {
    echo ""
    echo "📊 Container Status:"
    echo "==================="
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "✅ Visual Inspection Demo is running!"
    echo "  - Container: $CONTAINER_NAME"
    echo "  - URL: http://localhost:$PORT"
    echo "  - Image: $IMAGE_NAME"
    echo ""
    echo "📝 Useful Commands:"
    echo "  - View logs:        docker logs $CONTAINER_NAME -f"
    echo "  - Stop container:   docker stop $CONTAINER_NAME"
    echo "  - Start container:  docker start $CONTAINER_NAME"
    echo "  - Remove container: docker rm -f $CONTAINER_NAME"
    echo "  - Remove image:     docker rmi $IMAGE_NAME"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "  - Check logs: docker logs $CONTAINER_NAME"
    echo "  - Access shell: docker exec -it $CONTAINER_NAME /bin/bash"
}

# Main execution
main() {
    check_docker
    check_secrets
    stop_existing
    build_image
    run_container
    
    # Wait for container to be healthy
    echo ""
    echo "⏳ Waiting for application to start..."
    sleep 3
    
    show_status
}

# Run main function
main
