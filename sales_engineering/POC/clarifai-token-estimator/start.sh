#!/bin/bash

# start.sh: Script to start the Clarifai Token Estimator Streamlit app

set -e  # Exit on any error

echo "Starting Clarifai Token Estimator..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Please run ./setup-env.sh first."
    exit 1
fi

# Check if app is already running
if [ -f ".streamlit_pid" ]; then
    PID=$(cat .streamlit_pid)
    if kill -0 $PID 2>/dev/null; then
        echo "App is already running (PID: $PID)"
        exit 1
    else
        echo "Removing stale PID file..."
        rm .streamlit_pid
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Start Streamlit app in background
echo "Starting Streamlit app..."
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &
STREAMLIT_PID=$!

# Save PID to file
echo $STREAMLIT_PID > .streamlit_pid

echo "Streamlit app started with PID: $STREAMLIT_PID"
echo "App should be available at http://localhost:8501"
echo "To stop the app, run: ./stop.sh"