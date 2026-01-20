#!/bin/bash

# setup-env.sh: Script to set up Python virtual environment with Python 3.12

set -e  # Exit on any error

echo "Setting up Python virtual environment..."

# Check if Python 3.12 is available
if ! command -v python3.12 &> /dev/null; then
    echo "Error: Python 3.12 is not installed or not in PATH."
    echo "Please install Python 3.12 and try again."
    exit 1
fi

echo "Python 3.12 found: $(python3.12 --version)"

# Check if virtual environment already exists
if [ -d ".venv" ]; then
    echo "Virtual environment already exists. Removing it to recreate..."
    rm -rf .venv
fi

# Create virtual environment with Python 3.12
echo "Creating virtual environment with Python 3.12..."
python3.12 -m venv .venv

# Activate the virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing requirements from requirements.txt..."
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found. Skipping package installation."
fi

# Install dev requirements if requirements-dev.txt exists
if [ -f "requirements-dev.txt" ]; then
    echo "Installing dev requirements from requirements-dev.txt..."
    pip install -r requirements-dev.txt
else
    echo "Warning: requirements-dev.txt not found. Skipping dev package installation."
fi

echo "Virtual environment setup complete!"
echo "To activate the environment, run: source .venv/bin/activate"