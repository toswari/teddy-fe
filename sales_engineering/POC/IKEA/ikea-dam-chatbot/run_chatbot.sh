#!/bin/bash

# Clarifai Multimodal Chatbot Launcher
echo "🤖 Clarifai Multimodal Chatbot"
echo "================================"

# Check if required Python packages are available
echo "🔍 Checking required packages..."
python -c "import streamlit, clarifai, PIL, toml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Required packages not found. Please install them:"
    echo "pip install streamlit clarifai pillow python-dotenv toml"
    echo ""
    echo "Or if using conda:"
    echo "conda install streamlit clarifai pillow python-dotenv toml -c conda-forge"
    exit 1
fi

echo "✅ Required packages found"

# Check if .streamlit/secrets.toml file exists
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "❌ Streamlit secrets file not found. Please create it from the template:"
    echo "cp .streamlit/secrets.toml.example .streamlit/secrets.toml"
    echo "Then edit .streamlit/secrets.toml and add your Clarifai API key"
    exit 1
fi

# Check if Clarifai API key is set in secrets
if grep -q "your_clarifai_api_key_here" .streamlit/secrets.toml; then
    echo "❌ Clarifai API key not set properly in .streamlit/secrets.toml"
    echo "Please edit .streamlit/secrets.toml and replace 'your_clarifai_api_key_here' with your actual API key"
    echo "Get your API key from: https://clarifai.com/settings/security"
    exit 1
fi

# Test the setup
echo "🧪 Testing API connection..."
python test_setup.py
if [ $? -ne 0 ]; then
    echo "❌ API test failed. Please check your API key and internet connection."
    exit 1
fi

# Display environment info
echo "🐍 Python environment info:"
echo "Python path: $(which python)"
echo "Python version: $(python --version)"
echo "Streamlit path: $(which streamlit)"

# Start the chatbot
echo "🚀 Starting Clarifai Multimodal Chatbot..."
echo "📱 The chatbot will open in your web browser at http://localhost:8502"
echo "🛑 Press Ctrl+C to stop the chatbot"
echo ""

# Run with current Python environment on port 8502
streamlit run chatbot_app.py --server.port 8502
