#!/bin/bash
# Startup script for AI Brand Compliance Specialist

echo "Starting AI Brand Compliance Specialist..."
echo "========================================"

# Check if conda environment exists
if /home/toswari/anaconda3/bin/conda env list | grep -q "brand-logo-312"; then
    echo "✓ Conda environment 'brand-logo-312' found"
else
    echo "✗ Conda environment 'brand-logo-312' not found"
    echo "Please run: conda create -n brand-logo-312 python=3.12"
    exit 1
fi

# Start the Streamlit application
echo "Starting Streamlit application..."
/home/toswari/anaconda3/bin/conda run -n brand-logo-312 streamlit run app.py

echo "Application stopped."
