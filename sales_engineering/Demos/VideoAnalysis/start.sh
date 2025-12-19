#!/bin/bash

# Video Analysis Application Startup Script
# This script starts the Flask application

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print banner
echo "=========================================="
echo "  Video Analysis Platform - Startup"
echo "=========================================="
echo ""

# Configuration
CONDA_ENV_NAME="VideoAnalysis-311"

# Check if conda is available and activate environment
if command -v conda &> /dev/null; then
    # Initialize conda for bash/zsh
    eval "$(conda shell.bash hook)"
    
    # Check if the environment exists
    if conda env list | grep -q "^${CONDA_ENV_NAME} "; then
        print_info "Activating conda environment '${CONDA_ENV_NAME}'..."
        conda activate ${CONDA_ENV_NAME}
        
        if [ $? -eq 0 ]; then
            print_success "Conda environment activated"
            PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
            print_info "Python $PYTHON_VERSION"
        else
            print_error "Failed to activate conda environment"
            exit 1
        fi
    else
        print_error "Conda environment '${CONDA_ENV_NAME}' not found"
        print_info "Please run: ./setup-env.sh to create the environment"
        exit 1
    fi
else
    print_error "Conda not found"
    print_info "Please install conda or run: ./setup-env.sh"
    exit 1
fi

# Verify Flask is installed
if ! python -c "import flask" &> /dev/null; then
    print_error "Flask not installed"
    print_info "Please run: ./setup-env.sh to install dependencies"
    exit 1
fi

# Create necessary directories
mkdir -p uploads static

# Load environment variables
if [ -f ".env" ]; then
    print_success "Loading configuration from .env..."
    export $(grep -v '^#' .env | xargs)
    
    if [ -z "$CLARIFAI_USERNAME" ] || [ -z "$CLARIFAI_PAT" ]; then
        print_warning "Clarifai credentials not configured in .env"
    else
        print_success "Clarifai credentials loaded"
    fi
else
    print_warning ".env file not found"
    print_info "Please run: ./setup-env.sh to create .env template"
fi

# Check if port 5001 is available
print_info "Checking if port 5001 is available..."
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port 5001 is already in use"
    read -p "Would you like to kill the process using port 5001? (y/n): " kill_process
    
    if [ "$kill_process" = "y" ] || [ "$kill_process" = "Y" ]; then
        lsof -ti:5001 | xargs kill -9
        print_success "Process killed"
    else
        print_error "Cannot start application while port 5001 is in use"
        exit 1
    fi
else
    print_success "Port 5001 is available"
fi

# Start the application
echo ""
echo "=========================================="
print_success "Starting Video Analysis Application..."
echo "=========================================="
echo ""
print_info "Access the application at: ${GREEN}http://localhost:5001${NC}"
print_info "Press Ctrl+C to stop the server"
echo ""

# Start Flask app
export FLASK_APP=app.py

# Use FLASK_ENV from .env if set, otherwise default to development
if [ -z "$FLASK_ENV" ]; then
    export FLASK_ENV=development
fi

# Set FLASK_DEBUG if not already set
if [ -z "$FLASK_DEBUG" ]; then
    export FLASK_DEBUG=1
fi

print_info "Flask Environment: $FLASK_ENV"

python app.py
