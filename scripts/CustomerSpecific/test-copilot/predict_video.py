"""
Video Prediction Example
This script demonstrates how to use the MM-Poly-8B model for video-based predictions.
"""

from clarifai.client import Model
from clarifai.runners.utils.data_types import Video

def main():
    # Initialize the model
    model = Model(url="https://clarifai.com/clarifai/main/models/mm-poly-8b")
    
    # Define video URL
    video_url = "https://s3.amazonaws.com/samples.clarifai.com/beer.mp4"
    video_obj = Video(url=video_url)
    
    # Make a prediction with the video
    result = model.predict(
        prompt="Describe in detail what is in the video.",
        video=video_obj,
        max_tokens=1024,
    )
    
    # Print the result
    print("Video Predict response:", result)

if __name__ == "__main__":
    main()
