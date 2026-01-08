#!/bin/bash

# Setup script for VideoAnalysis conda environment
# This script creates a conda environment with Python 3.11 and installs all required dependencies

set -e  # Exit on error

ENV_NAME="VideoDetection-312"
PYTHON_VERSION="3.12"

echo "=========================================="
echo "Setting up VideoDetection Conda Environment"
echo "=========================================="
echo ""

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "Error: conda is not installed or not in PATH"
    echo "Please install Anaconda or Miniconda first"
    exit 1
fi

# Check if environment already exists
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Environment '${ENV_NAME}' already exists."
    read -p "Do you want to remove and recreate it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing environment..."
        conda env remove -n ${ENV_NAME} -y
    else
        echo "Exiting without changes."
        exit 0
    fi
fi

# Create conda environment
echo "Creating conda environment: ${ENV_NAME} with Python ${PYTHON_VERSION}..."
conda create -n ${ENV_NAME} python=${PYTHON_VERSION} -y

# Activate environment
echo "Activating environment..."
eval "$(conda shell.bash hook)"
conda activate ${ENV_NAME}

# Install pkg-config (required for PyAV on macOS)
echo "Installing pkg-config (required for building PyAV)..."
if command -v brew &> /dev/null; then
    brew install pkg-config
else
    echo "Warning: Homebrew not found. Please install pkg-config manually for PyAV."
fi

# Install pip packages from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "Installing packages from requirements.txt..."
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To activate the environment, run:"
echo "  conda activate ${ENV_NAME}"
echo ""
echo "To deactivate, run:"
echo "  conda deactivate"
echo ""
