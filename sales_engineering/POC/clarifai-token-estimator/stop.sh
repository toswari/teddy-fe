#!/bin/bash

# stop.sh: Script to stop the Clarifai Token Estimator Streamlit app

set -e  # Exit on any error

echo "Stopping Clarifai Token Estimator..."

# Check if PID file exists
if [ ! -f ".streamlit_pid" ]; then
    echo "No PID file found. App may not be running."
    exit 1
fi

# Read PID from file
PID=$(cat .streamlit_pid)

# Check if process is still running
if ! kill -0 $PID 2>/dev/null; then
    echo "Process with PID $PID is not running. Removing stale PID file..."
    rm .streamlit_pid
    exit 1
fi

# Kill the process
echo "Stopping Streamlit app (PID: $PID)..."
kill $PID

# Wait a bit for graceful shutdown
sleep 2

# Check if it's still running and force kill if necessary
if kill -0 $PID 2>/dev/null; then
    echo "Process still running, force killing..."
    kill -9 $PID
fi

# Remove PID file
rm .streamlit_pid

echo "Streamlit app stopped successfully."