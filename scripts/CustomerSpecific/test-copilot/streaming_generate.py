"""
Streaming/Generate Example
This script demonstrates how to use the MM-Poly-8B model with streaming responses.
"""

from clarifai.client import Model

def main():
    # Initialize the model
    model = Model(url="https://clarifai.com/clarifai/main/models/mm-poly-8b")
    
    # Generate streaming response
    print("Generate response:")
    for chunk in model.generate(prompt="Discuss the implications of AI in modern healthcare."):
        print(chunk, end='', flush=True)
    print()  # New line at the end

if __name__ == "__main__":
    main()
