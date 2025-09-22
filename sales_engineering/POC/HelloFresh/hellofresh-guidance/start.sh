#!/bin/bash
# Startup script for AI Brand Compliance Specialist

echo "🚀 Starting AI Brand Compliance Specialist..."
echo "============================================="

# Define paths
CONDA_PATH="/home/toswari/anaconda3/bin/conda"
ENV_NAME="brand-logo-312"

# Check if conda environment exists
if $CONDA_PATH env list | grep -q "$ENV_NAME"; then
    echo "✓ Conda environment '$ENV_NAME' found"
else
    echo "✗ Conda environment '$ENV_NAME' not found"
    echo "📦 Please run: conda create -n $ENV_NAME python=3.12"
    echo "📦 Or use: ./conda_run.sh check"
    exit 1
fi

# Check if requirements are installed
echo "🔍 Checking dependencies..."
if $CONDA_PATH run -n $ENV_NAME python -c "import streamlit" 2>/dev/null; then
    echo "✓ Dependencies appear to be installed"
else
    echo "⚠️  Dependencies may be missing"
    echo "📦 Run: ./conda_run.sh install"
    echo "📦 Or: conda activate $ENV_NAME && pip install -r requirements.txt"
fi

# Start the Streamlit application
echo "🌟 Starting Streamlit application with conda environment '$ENV_NAME'..."
$CONDA_PATH run -n $ENV_NAME streamlit run app.py

echo "Application stopped."
