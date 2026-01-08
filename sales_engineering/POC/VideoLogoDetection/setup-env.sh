#!/bin/bash
set -euo pipefail

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

REQUIRED_BINARIES=(podman ffmpeg)

detect_platform() {
    local os_name
    os_name=$(uname -s)
    case "${os_name}" in
        Darwin)
            echo "macos"
            ;;
        Linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

install_linux_packages() {
    local packages=("$@")
    if ! command -v apt-get &> /dev/null; then
        print_warning "apt-get unavailable; install ${packages[*]} manually"
        return
    fi
    print_info "Refreshing apt repositories"
    sudo apt-get update -y
    print_info "Installing ${packages[*]} via apt-get"
    sudo apt-get install -y "${packages[@]}"
}

install_macos_packages() {
    local packages=("$@")
    if ! command -v brew &> /dev/null; then
        print_warning "Homebrew not installed; install it from https://brew.sh and re-run"
        return
    fi
    print_info "Installing ${packages[*]} via Homebrew"
    brew install "${packages[@]}"
}

ensure_required_software() {
    local platform="$1"
    local missing=()
    for bin in "${REQUIRED_BINARIES[@]}"; do
        if ! command -v "${bin}" &> /dev/null; then
            missing+=("${bin}")
        fi
    done
    if [ ${#missing[@]} -eq 0 ]; then
        print_success "All required binaries present: ${REQUIRED_BINARIES[*]}"
        return
    fi
    print_warning "Missing required tools: ${missing[*]}"
    case "${platform}" in
        macos)
            install_macos_packages "${missing[@]}"
            ;;
        wsl|linux)
            install_linux_packages "${missing[@]}"
            ;;
        *)
            print_warning "Please install ${missing[*]} manually for your platform"
            ;;
    esac
}

check_podman_desktop() {
    if command -v podman-desktop &> /dev/null; then
        print_success "Podman Desktop detected"
        return
    fi
    print_warning "Podman Desktop not found. Install it from https://podman-desktop.io to manage containers graphically."
}

check_docker_extension() {
    if ! command -v podman &> /dev/null; then
        return
    fi
    if podman extension list 2>/dev/null | grep -q "docker"; then
        print_success "Podman Docker extension enabled"
    else
        print_warning "Podman Docker extension is missing; run 'podman extension install docker' inside Podman Desktop to enable Docker compatibility."
    fi
}

install_podman_compose_macos() {
    if ! command -v brew &> /dev/null; then
        print_warning "Homebrew not installed; install it to automatically set up podman-compose."
        return
    fi
    print_info "Installing podman-compose via Homebrew"
    brew install podman-compose
}

install_podman_compose_linux() {
    if command -v apt-get &> /dev/null; then
        print_info "Installing podman-compose via apt"
        sudo apt-get update -y
        sudo apt-get install -y podman-compose
        return
    fi
    print_warning "apt-get not found; installing podman-compose via pip (user install)"
    pip3 install --user podman-compose
}

ensure_podman_compose() {
    if command -v podman-compose &> /dev/null; then
        print_success "podman-compose is available"
        return
    fi
    print_info "podman-compose not found; attempting to install it"
    case "$1" in
        macos)
            install_podman_compose_macos
            ;;
        linux|wsl)
            install_podman_compose_linux
            ;;
        *)
            print_warning "Automatic podman-compose install not supported on '$1'; install it manually."
            ;;
    esac
    if ! command -v podman-compose &> /dev/null; then
        print_error "podman-compose installation did not succeed; please install it before rerunning this script."
        exit 1
    fi
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Print banner
echo "=========================================="
echo "  Video Analysis - Environment Setup"
echo "=========================================="
echo ""

# Configuration
CONDA_ENV_NAME="VideoDetection-312"
PYTHON_VERSION="3.12"
CONDA_SETUP_SCRIPT="${SCRIPT_DIR}/setup-conda-env.sh"
SETUP_DATABASE_SCRIPT="${SCRIPT_DIR}/setup-database.sh"
PLATFORM=$(detect_platform)
print_info "Detected platform: ${PLATFORM}"
ensure_required_software "${PLATFORM}"
check_podman_desktop
check_docker_extension
ensure_podman_compose "${PLATFORM}"

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

if [ ! -f "${CONDA_SETUP_SCRIPT}" ]; then
    print_error "Missing support script: ${CONDA_SETUP_SCRIPT}"
    exit 1
fi

print_info "Delegating Conda creation to setup-conda-env.sh"
bash "${CONDA_SETUP_SCRIPT}"
print_success "Conda environment '${CONDA_ENV_NAME}' (Python ${PYTHON_VERSION}) ready"

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
    if [ ! -f "${SETUP_DATABASE_SCRIPT}" ]; then
        print_error "Database helper script not found at ${SETUP_DATABASE_SCRIPT}."
    else
        print_info "Delegating database recreation to setup-database.sh"
        bash "${SETUP_DATABASE_SCRIPT}"
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
