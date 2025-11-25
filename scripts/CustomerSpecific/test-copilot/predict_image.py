"""
Image Prediction Example
This script demonstrates how to use the MM-Poly-8B model for image-based predictions.
"""

from clarifai.client import Model
from clarifai.runners.utils.data_types import Image

def main():
    # Initialize the model
    model = Model(url="https://clarifai.com/clarifai/main/models/mm-poly-8b")
    
    # Define image URL
    image_url = "https://samples.clarifai.com/metro-north.jpg"
    image_obj = Image(url=image_url)
    
    # Make a prediction with the image
    result = model.predict(
        prompt="Describe this image.",
        image=image_obj,
        max_tokens=1024,
    )
    
    # Print the result
    print("Image Predict response:", result)

if __name__ == "__main__":
    main()
