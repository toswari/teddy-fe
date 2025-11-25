"""
Text Prediction Example
This script demonstrates how to use the MM-Poly-8B model for text-based predictions.
"""

from clarifai.client import Model

def main():
    # Initialize the model
    model = Model(url="https://clarifai.com/clarifai/main/models/mm-poly-8b")
    
    # Define the prompt
    prompt = "What are the key differences between classical and quantum computing?"
    
    # Make a prediction
    result = model.predict(prompt)
    
    # Print the result
    print("Predict response:", result)

if __name__ == "__main__":
    main()
