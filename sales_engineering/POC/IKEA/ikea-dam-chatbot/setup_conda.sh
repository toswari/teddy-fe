#!/bin/bash

# Quick setup using conda environment.yml file
echo "🚀 Setting up Clarifai Chatbot with conda environment.yml..."

# Initialize conda
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

# Create environment from yml file
echo "📦 Creating conda environment from environment.yml..."
conda env create -f environment.yml

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
echo "3. Run the chatbot with: ./run_chatbot.sh"
echo ""
echo "🏃 To start the chatbot:"
echo "   conda activate clarifai-chatbot"
echo "   streamlit run chatbot_app.py"
