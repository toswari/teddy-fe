#!/bin/bash

# Load environment variables from .env file (skip comments)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
    echo "Environment variables loaded from .env"
else
    echo "Warning: .env file not found"
fi

# Check if CLARIFAI_PAT is set
if [ -z "$CLARIFAI_PAT" ]; then
    echo "Error: CLARIFAI_PAT environment variable is not set"
    exit 1
fi

# Check if CLARIFAI_USER_ID is set
if [ -z "$CLARIFAI_USER_ID" ]; then
    echo "Error: CLARIFAI_USER_ID environment variable is not set"
    exit 1
fi

echo "CLARIFAI_PAT: ${CLARIFAI_PAT:0:10}..."
echo "CLARIFAI_USER_ID: ${CLARIFAI_USER_ID}"

# Set up non-interactive authentication for the container environment
echo "Setting up Clarifai authentication for containerized environment..."

# Create the config directory if it doesn't exist
mkdir -p ~/.clarifai

# Write the config file directly with the PAT
cat > ~/.clarifai/config.yaml << EOF
contexts:
  default:
    api_url: https://api.clarifai.com
    pat: ${CLARIFAI_PAT}
    user_id: ${CLARIFAI_USER_ID}
current_context: default
EOF

echo "Authentication config created successfully"

# Start the local runner with automatic yes response to all prompts
echo "Starting Clarifai iPhone Layout MCP local runner..."
echo "This will automatically create compute cluster and nodepool if they don't exist"
yes | clarifai model local-runner .