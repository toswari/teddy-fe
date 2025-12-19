#!/bin/bash

# Visual Inspection Demo - Start Script
# This script starts the Streamlit application

echo "Starting Visual Inspection Demo..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed or not in PATH"
    exit 1
fi

# Check if requirements are installed
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Get the port number (default: 8520)
PORT=${1:-8520}

# Start Streamlit in the background and save the PID
echo "Starting Streamlit on port $PORT..."
nohup streamlit run app.py --server.port=$PORT > streamlit.log 2>&1 &
STREAMLIT_PID=$!

# Save the PID to a file for the stop script
echo $STREAMLIT_PID > .streamlit.pid

# Wait a moment for the server to start
sleep 2

# Check if the process is running
if ps -p $STREAMLIT_PID > /dev/null; then
    echo "✓ Visual Inspection Demo started successfully!"
    echo "  - PID: $STREAMLIT_PID"
    echo "  - URL: http://localhost:$PORT"
    echo "  - Log file: streamlit.log"
    echo ""
    echo "To stop the application, run: ./stop.sh"
else
    echo "✗ Failed to start the application. Check streamlit.log for errors."
    exit 1
fi
