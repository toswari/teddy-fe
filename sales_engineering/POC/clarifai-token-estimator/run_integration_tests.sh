#!/bin/bash
# Quick script to run integration tests with Clarifai API
# Usage: ./run_integration_tests.sh

set -e

if [ -z "$CLARIFAI_PAT" ]; then
    echo "Error: CLARIFAI_PAT environment variable is not set"
    echo ""
    echo "Please set it before running integration tests:"
    echo "  export CLARIFAI_PAT=your_personal_access_token"
    echo ""
    echo "Or run with:"
    echo "  CLARIFAI_PAT=your_pat ./run_integration_tests.sh"
    exit 1
fi

echo "Running integration tests with Clarifai API..."
echo "Using sample.png for image description with GPT-4o and GPT-5.1"
echo ""

PYTHONPATH=. python -m pytest tests/test_integration_image_description.py -v -s

echo ""
echo "Integration tests completed!"
