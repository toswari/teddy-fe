#!/bin/bash

# Clarifai Multimodal Chatbot Setup Script
echo "🚀 Setting up Clarifai Multimodal Chatbot..."

# Initialize conda for bash
if [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
elif [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
elif [ -f /opt/conda/etc/profile.d/conda.sh ]; then
    source /opt/conda/etc/profile.d/conda.sh
fi

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Conda is not installed. Please install Anaconda or Miniconda."
    echo "Download from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Create conda environment
echo "📦 Creating conda environment 'clarifai-chatbot'..."
conda create -n clarifai-chatbot python=3.11 -y

# Activate conda environment
echo "🔄 Activating conda environment..."
conda activate clarifai-chatbot

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements using conda and pip
echo "📥 Installing requirements..."
# Install conda packages first
conda install -c conda-forge streamlit pillow -y
# Install clarifai and other packages with pip
pip install clarifai>=11.6.0 python-dotenv>=1.0.0 toml>=0.10.2

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️ Creating .env file..."
    cp .env.example .env
    echo "✏️ Please edit .env file and add your Clarifai API key"
fi

# Create Streamlit secrets file if it doesn't exist
if [ ! -f .streamlit/secrets.toml ]; then
    echo "🔐 Creating Streamlit secrets file..."
    cp .streamlit/secrets.toml.example .streamlit/secrets.toml
    echo "✏️ Please edit .streamlit/secrets.toml and add your Clarifai API key"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🔑 Next steps:"
echo "1. Get your Clarifai API key from: https://clarifai.com/settings/security"
echo "2. Edit .streamlit/secrets.toml and replace 'your_clarifai_api_key_here' with your actual API key"
echo "3. Run the chatbot with: streamlit run chatbot_app.py"
echo ""
echo "🏃 To start the chatbot:"
echo "   conda activate clarifai-chatbot"
echo "   streamlit run chatbot_app.py"
