#!/bin/bash

# Video Analysis Application - Environment Setup Script
# This script sets up the conda environment and installs dependencies

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
echo "  Video Analysis - Environment Setup"
echo "=========================================="
echo ""

# Configuration
CONDA_ENV_NAME="VideoAnalysis-311"
PYTHON_VERSION="3.11"

# Check if conda is available
print_info "Checking for conda..."
if ! command -v conda &> /dev/null; then
    print_error "Conda not found. Please install Anaconda or Miniconda first."
    echo ""
    print_info "Download from:"
    echo "  - Anaconda: https://www.anaconda.com/download"
    echo "  - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

print_success "Conda found: $(conda --version)"

# Initialize conda for bash/zsh
print_info "Initializing conda for shell..."
eval "$(conda shell.bash hook)"

# Check if environment already exists
print_info "Checking for existing environment '${CONDA_ENV_NAME}'..."
if conda env list | grep -q "^${CONDA_ENV_NAME} "; then
    print_warning "Environment '${CONDA_ENV_NAME}' already exists"
    read -p "Would you like to recreate it? (y/n): " recreate
    
    if [ "$recreate" = "y" ] || [ "$recreate" = "Y" ]; then
        print_info "Removing existing environment..."
        conda env remove -n ${CONDA_ENV_NAME} -y
        print_success "Environment removed"
    else
        print_info "Using existing environment"
        conda activate ${CONDA_ENV_NAME}
        
        if [ $? -eq 0 ]; then
            print_success "Environment activated"
            CURRENT_PYTHON=$(python --version 2>&1 | awk '{print $2}')
            print_info "Current Python version: $CURRENT_PYTHON"
        else
            print_error "Failed to activate environment"
            exit 1
        fi
        
        # Skip to dependency installation
        SKIP_ENV_CREATION=true
    fi
fi

# Create conda environment if needed
if [ "$SKIP_ENV_CREATION" != "true" ]; then
    print_info "Creating conda environment '${CONDA_ENV_NAME}' with Python ${PYTHON_VERSION}..."
    conda create -n ${CONDA_ENV_NAME} python=${PYTHON_VERSION} -y
    
    if [ $? -eq 0 ]; then
        print_success "Environment created successfully"
    else
        print_error "Failed to create environment"
        exit 1
    fi
    
    # Activate the new environment
    print_info "Activating environment..."
    conda activate ${CONDA_ENV_NAME}
    
    if [ $? -eq 0 ]; then
        print_success "Environment activated"
        CURRENT_PYTHON=$(python --version 2>&1 | awk '{print $2}')
        print_success "Python $CURRENT_PYTHON ready"
    else
        print_error "Failed to activate environment"
        exit 1
    fi
fi

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip
print_success "Pip upgraded"

# Install dependencies
if [ -f "requirements.txt" ]; then
    print_info "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
    
    if [ $? -eq 0 ]; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
else
    print_warning "requirements.txt not found"
    print_info "Please create a requirements.txt file with your dependencies"
fi

# Create necessary directories
print_info "Creating application directories..."
mkdir -p uploads
mkdir -p static
print_success "Directories created"

# Setup .env file
if [ ! -f ".env" ]; then
    print_info "Creating .env template..."
    
    cat > .env << EOF
# Clarifai API Credentials
# Get your credentials from: https://clarifai.com/settings/security
CLARIFAI_USERNAME=your_username_here
CLARIFAI_PAT=your_personal_access_token_here

# Flask Configuration (optional)
FLASK_ENV=development
FLASK_DEBUG=1
EOF
    
    print_success ".env template created"
    print_warning "Please edit .env file and add your Clarifai credentials"
    print_info "  1. Open .env file in your editor"
    print_info "  2. Replace 'your_username_here' with your Clarifai username"
    print_info "  3. Replace 'your_personal_access_token_here' with your PAT"
else
    print_success ".env file already exists"
fi

# Database configuration for local single-user POC (matches podman-compose.yaml)
print_info "Configuring database environment variables for VideoLogoDetection..."
export DB_USER="videologo_user"
export DB_PASSWORD="videologo_pass"
export DB_NAME="videologo_db"
export DB_HOST="localhost"
export DB_PORT="35432"  # non-standard host port exposed by podman Postgres

export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

print_success "Database environment configured:"
echo "  DB_USER=${DB_USER}"
echo "  DB_NAME=${DB_NAME}"
echo "  DB_HOST=${DB_HOST}"
echo "  DB_PORT=${DB_PORT}"

# Optionally recreate the database (drop + create) inside the Podman container
print_info "Do you want to recreate the database '${DB_NAME}' inside the 'videologo_db' Podman container? (This will drop and re-create it.)"
read -p "Recreate database? (y/n): " recreate_db

if [ "$recreate_db" = "y" ] || [ "$recreate_db" = "Y" ]; then
    if ! command -v podman &> /dev/null; then
        print_error "podman command not found. Install Podman to use the recreate option."
    else
        print_info "Recreating database '${DB_NAME}' inside container 'videologo_db'..."
        podman exec -e PGPASSWORD="${DB_PASSWORD}" videologo_db psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME};" && \
        podman exec -e PGPASSWORD="${DB_PASSWORD}" videologo_db psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${DB_NAME};"

        if [ $? -eq 0 ]; then
            print_success "Database '${DB_NAME}' recreated successfully inside container."
        else
            print_error "Failed to recreate database '${DB_NAME}'. Ensure the 'videologo_db' container is running (podman-compose up -d db)."
        fi
    fi
else
    print_info "Keeping existing database '${DB_NAME}'."
fi

# Display summary
echo ""
echo "=========================================="
print_success "Environment Setup Complete!"
echo "=========================================="
echo ""
print_info "Next steps:"
echo "  1. Start Postgres via Podman:"
echo "     podman-compose up -d db"
echo "  2. Activate the environment (if not already):"
echo "     conda activate ${CONDA_ENV_NAME}"
echo "  3. Start the application:"
echo "     ./start.sh"
echo ""
print_info "To deactivate the environment, run:"
echo "  conda deactivate"
echo ""
