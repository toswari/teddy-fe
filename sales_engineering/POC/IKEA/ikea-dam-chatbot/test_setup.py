#!/usr/bin/env python3
"""
Simple demo script to test the multimodal functionality
Run this to verify your setup before using the full chatbot
"""

import os
import sys
import toml
from clarifai.client.model import Model
from clarifai.client.input import Inputs

def load_secrets():
    """Load API key from Streamlit secrets or environment variables"""
    secrets_path = ".streamlit/secrets.toml"
    
    # Try to load from Streamlit secrets first
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, 'r') as f:
                secrets = toml.load(f)
                pat = secrets.get("clarifai", {}).get("PAT")
                if pat and pat != "your_clarifai_api_key_here":
                    return pat
        except Exception as e:
            print(f"Warning: Could not read secrets file: {e}")
    
    # Fallback to environment variable
    pat = os.getenv('CLARIFAI_PAT')
    if pat:
        return pat
    
    return None

def test_multimodal():
    """Test basic multimodal functionality"""
    
    # Check API key
    pat = load_secrets()
    if not pat:
        print("❌ Please set your Clarifai API key")
        print("Option 1: Edit .streamlit/secrets.toml")
        print("Option 2: Set CLARIFAI_PAT environment variable")
        print("Get your API key from: https://clarifai.com/settings/security")
        return False
    
    print("🤖 Testing Clarifai Multimodal API...")
    print("📷 Using sample image: metro-north train")
    print("❓ Question: 'What do you see in this image?'")
    
    try:
        # Create multimodal input
        multi_inputs = Inputs.get_multimodal_input(
            input_id="",
            image_url="https://samples.clarifai.com/metro-north.jpg",
            raw_text="What do you see in this image?"
        )
        
        # Test with MiniCPM model
        model_url = "https://clarifai.com/openbmb/miniCPM/models/MiniCPM-o-2_6-language"
        model = Model(url=model_url, pat=pat)
        
        print("🔍 Processing...")
        prediction = model.predict(inputs=[multi_inputs])
        
        if prediction.outputs and prediction.outputs[0].data.text:
            response = prediction.outputs[0].data.text.raw
            print("\n✅ Success!")
            print(f"🤖 AI Response: {response}")
            return True
        else:
            print("❌ No response from model")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_multimodal()
    if success:
        print("\n🎉 Setup is working correctly!")
        print("You can now run the full chatbot with: streamlit run chatbot_app.py")
    else:
        print("\n🔧 Please check your setup and try again")
        sys.exit(1)
