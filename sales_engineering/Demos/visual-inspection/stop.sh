#!/bin/bash

# Visual Inspection Demo - Stop Script
# This script stops the running Streamlit application

echo "Stopping Visual Inspection Demo..."

# Check if PID file exists
if [ ! -f .streamlit.pid ]; then
    echo "No PID file found. The application may not be running."
    echo "Attempting to find and stop any running Streamlit processes..."
    
    # Try to find and kill streamlit processes
    pkill -f "streamlit run app.py"
    
    if [ $? -eq 0 ]; then
        echo "✓ Stopped Streamlit processes"
    else
        echo "No running Streamlit processes found."
    fi
    exit 0
fi

# Read the PID from the file
STREAMLIT_PID=$(cat .streamlit.pid)

# Check if the process is running
if ps -p $STREAMLIT_PID > /dev/null 2>&1; then
    # Kill the process
    kill $STREAMLIT_PID
    
    # Wait a moment and check if it's stopped
    sleep 1
    
    if ps -p $STREAMLIT_PID > /dev/null 2>&1; then
        echo "Process didn't stop gracefully, forcing termination..."
        kill -9 $STREAMLIT_PID
    fi
    
    echo "✓ Visual Inspection Demo stopped successfully (PID: $STREAMLIT_PID)"
else
    echo "Process with PID $STREAMLIT_PID is not running."
fi

# Clean up the PID file
rm -f .streamlit.pid

# Also try to stop any other streamlit processes for this app
pkill -f "streamlit run app.py"

echo "Cleanup complete."
