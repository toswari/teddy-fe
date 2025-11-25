"""
Audio Prediction Example
This script demonstrates how to use the MM-Poly-8B model for audio-based predictions.
"""

from clarifai.client import Model
from clarifai.runners.utils.data_types import Audio

def main():
    # Initialize the model
    model = Model(url="https://clarifai.com/clarifai/main/models/mm-poly-8b")
    
    # Define audio URL
    audio_url = "https://samples.clarifai.com/GoodMorning.wav"
    audio_obj = Audio(url=audio_url)
    
    # Make a prediction with the audio
    result = model.predict(
        prompt="Describe in detail what is in the audio.",
        audio=audio_obj,
        max_tokens=1024,
    )
    
    # Print the result
    print("Audio Predict response:", result)

if __name__ == "__main__":
    main()
