"""
OpenAI-Compatible API Usage Example
This script demonstrates how to use the MM-Poly-8B model via Clarifai's OpenAI-compatible API endpoint.
"""

import os
from openai import OpenAI

def main():
    # Initialize OpenAI client with Clarifai credentials
    client = OpenAI(
        api_key=os.getenv("CLARIFAI_PAT"),  # Get Clarifai PAT from environment variable
        base_url="https://api.clarifai.com/v2/ext/openai/v1"
    )

    # Make a chat completion request
    response = client.chat.completions.create(
        model="https://clarifai.com/clarifai/main/models/mm-poly-8b",
        messages=[
            {"role": "user", "content": "Can you explain the concept of quantum entanglement?"}
        ],
        max_completion_tokens=100,
    )
    
    # Print the response
    print("OpenAI-Compatible API Response:")
    print(response.choices[0].message.content)

if __name__ == "__main__":
    main()
