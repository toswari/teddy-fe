"""Integration test for Clarifai image description using OpenAI client pattern."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest
import requests
from openai import OpenAI

try:
    from clarifai_token_estimator.gemini_generate import GeminiGenerateClient
    HAS_CLARIFAI_SDK = True
except ImportError:
    HAS_CLARIFAI_SDK = False

# Mark as integration test - requires CLARIFAI_PAT env var
pytestmark = pytest.mark.skipif(
    not os.environ.get("CLARIFAI_PAT"),
    reason="CLARIFAI_PAT environment variable not set - skipping integration test",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE_PATH = PROJECT_ROOT / "sample.png"


def get_image_base64_from_url(image_url: str) -> str:
    """Download image from URL and convert to base64-encoded string."""
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    return base64.b64encode(response.content).decode("utf-8")


def get_image_base64_from_file(path: Path) -> str:
    """Load local image file and convert to base64-encoded string."""
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def test_gpt4o_image_description_with_sample_png() -> None:
    """Test image description using GPT-4o with sample.png - following Clarifai example."""
    if not SAMPLE_IMAGE_PATH.exists():
        pytest.skip(f"Sample image not found at {SAMPLE_IMAGE_PATH}")
    
    # Load local image file and convert to base64
    image_base64 = get_image_base64_from_file(SAMPLE_IMAGE_PATH)
    
    print(f"\n{'='*60}")
    print(f"Test 1: Local Image Input")
    print(f"{'='*60}")
    print(f"Model: openai/chat-completion/models/gpt-4o")
    print(f"Image: {SAMPLE_IMAGE_PATH}")
    print(f"Prompt: Describe this image in detail. What do you see?")
    print(f"Max tokens: 500")
    print(f"Temperature: 0.7")
    print(f"{'='*60}\n")
    
    # Initialize OpenAI client using Clarifai's OpenAI-compatible endpoint
    client = OpenAI(
        base_url="https://api.clarifai.com/v2/ext/openai/v1",
        api_key=os.environ["CLARIFAI_PAT"],
    )
    
    # Use GPT-4o which is more reliable for this test
    response = client.chat.completions.create(
        model="openai/chat-completion/models/gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in detail. What do you see?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    # Output the result
    content = response.choices[0].message.content
    
    # Assert
    assert response is not None, "Response should not be None"
    assert content is not None, "Response content should not be None"
    assert len(content) > 0, "Description should contain text"
    
    # Check usage metrics if available
    if response.usage:
        assert response.usage.total_tokens > 0, "Should have token usage"
    
    # Print for manual verification
    print(f"\n{'='*60}")
    print(f"Test 1: Inference Result")
    print(f"{'='*60}")
    print(f"Model: {response.model}")
    print(f"Response ID: {response.id}")
    print(f"\nOutput:\n{content}")
    if response.usage:
        print(f"\nUsage:")
        print(f"  Prompt tokens: {response.usage.prompt_tokens}")
        print(f"  Completion tokens: {response.usage.completion_tokens}")
        print(f"  Total tokens: {response.usage.total_tokens}")
    print(f"{'='*60}\n")


def test_gpt4o_streaming_image_description() -> None:
    """Test streaming image description with GPT-4o - following Clarifai example."""
    if not SAMPLE_IMAGE_PATH.exists():
        pytest.skip(f"Sample image not found at {SAMPLE_IMAGE_PATH}")
    
    # Load local image file and convert to base64
    image_base64 = get_image_base64_from_file(SAMPLE_IMAGE_PATH)
    
    print(f"\n{'='*60}")
    print(f"Test 2: Streaming Input")
    print(f"{'='*60}")
    print(f"Model: openai/chat-completion/models/gpt-4o")
    print(f"Image: {SAMPLE_IMAGE_PATH}")
    print(f"Prompt: What are the main elements in this image?")
    print(f"Max tokens: 300")
    print(f"Temperature: 0.7")
    print(f"Stream: True")
    print(f"{'='*60}\n")
    
    # Initialize OpenAI client using Clarifai's OpenAI-compatible endpoint
    client = OpenAI(
        base_url="https://api.clarifai.com/v2/ext/openai/v1",
        api_key=os.environ["CLARIFAI_PAT"],
    )
    
    # Use GPT-4o for more reliable streaming
    response = client.chat.completions.create(
        model="openai/chat-completion/models/gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What are the main elements in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.7,
        max_tokens=300,
        stream=True,
    )
    
    # Collect streaming chunks
    chunks = []
    for chunk in response:
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                chunks.append(delta.content)
    
    # Assert
    assert len(chunks) > 0, "Should have received streaming chunks"
    
    full_response = "".join(chunks)
    assert len(full_response) > 0, "Concatenated response should not be empty"
    
    print(f"\n{'='*60}")
    print(f"Test 2: Inference Result (Streaming)")
    print(f"{'='*60}")
    print(f"Chunks received: {len(chunks)}")
    print(f"\nOutput:\n{full_response}")
    print(f"{'='*60}\n")


def test_remote_image_url_description() -> None:
    """Test image description using remote URL - following Clarifai example pattern."""
    # Option 2: Download image from URL and convert to base64
    image_url = "https://samples.clarifai.com/cat1.jpeg"
    
    print(f"\n{'='*60}")
    print(f"Test 3: Remote Image Input")
    print(f"{'='*60}")
    print(f"Model: https://clarifai.com/openai/chat-completion/models/gpt-4o")
    print(f"Image URL: {image_url}")
    print(f"Prompt: Describe the image")
    print(f"Max tokens: 1024")
    print(f"Temperature: 0.7")
    print(f"{'='*60}\n")
    
    image_base64 = get_image_base64_from_url(image_url)
    
    # Initialize OpenAI client using Clarifai's OpenAI-compatible endpoint
    client = OpenAI(
        base_url="https://api.clarifai.com/v2/ext/openai/v1",
        api_key=os.environ["CLARIFAI_PAT"],
    )
    
    response = client.chat.completions.create(
        model="https://clarifai.com/openai/chat-completion/models/gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the image"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        temperature=0.7,
        max_tokens=1024
    )
    
    # Output the result
    content = response.choices[0].message.content
    
    # Assert
    assert content is not None, "Response content should not be None"
    assert len(content) > 0, "Description should contain text"
    assert "cat" in content.lower() or "animal" in content.lower() or "feline" in content.lower(), \
        "Description should mention the cat"
    
    print(f"\n{'='*60}")
    print(f"Test 3: Inference Result")
    print(f"{'='*60}")
    print(f"Model: {response.model}")
    print(f"\nOutput:\n{content}")
    if response.usage:
        print(f"\nUsage:")
        print(f"  Prompt tokens: {response.usage.prompt_tokens}")
        print(f"  Completion tokens: {response.usage.completion_tokens}")
        print(f"  Total tokens: {response.usage.total_tokens}")
    print(f"{'='*60}\n")


@pytest.mark.skipif(not HAS_CLARIFAI_SDK, reason="Clarifai SDK not installed")
def test_gemini_pro_image_with_native_sdk() -> None:
    """Test Gemini 2.5 Pro with image using native Clarifai SDK - following gemini-pro-example.py."""
    
    image_url = "https://samples.clarifai.com/metro-north.jpg"
    
    print(f"\n{'='*60}")
    print(f"Test 4: Gemini 2.5 Pro Image Input (Native SDK)")
    print(f"{'='*60}")
    print(f"Model: https://clarifai.com/gcp/generate/models/gemini-2_5-pro")
    print(f"Image URL: {image_url}")
    print(f"Prompt: Describe this image.")
    print(f"Max tokens: 1024")
    print(f"Temperature: 0.5")
    print(f"{'='*60}\n")
    
    try:
        generator = GeminiGenerateClient(
            pat=os.environ["CLARIFAI_PAT"],
            model_url="https://clarifai.com/gcp/generate/models/gemini-2_5-pro",
        )
        print("✓ GeminiGenerateClient initialized")

        print(f"\n⚡ Calling generate()...")
        result = generator.generate(
            prompt="Describe this image.",
            image_url=image_url,
            max_tokens=1024,
            temperature=0.5,
        )

        print(f"\n✓ generate() stream completed with {result.chunk_count} chunks")

        # Assert
        assert result is not None, "Result should not be None"
        assert result.text, "Response text should not be empty"
        assert len(result.text) > 0, "Response should contain text"
        assert result.usage is not None, "Usage estimates should be available"
        assert result.usage["total_tokens"] > 0, "Total tokens should be positive"
        
        print(f"\n{'='*60}")
        print(f"Test 4: Inference Result (Gemini 2.5 Pro)")
        print(f"{'='*60}")
        print(f"Chunks: {result.chunk_count}")
        print(f"TTFT: {result.ttft_ms or 'n/a'} ms")
        print(f"Total time: {result.total_time_ms:.2f} ms")
        if result.usage:
            print(
                "Estimated tokens -> "
                f"prompt: {result.usage['prompt_tokens']} | "
                f"completion: {result.usage['completion_tokens']} | "
                f"total: {result.usage['total_tokens']}"
            )
        print(f"\nOutput:\n{result.text}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERROR DETAILS")
        print(f"{'='*60}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"\nFull error:")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        raise


def test_gpt51_text_completion() -> None:
    """Test GPT-5.1 with text-only input."""
    
    print(f"\n{'='*60}")
    print(f"Test 5: GPT-5.1 Text Input")
    print(f"{'='*60}")
    print(f"Model: openai/chat-completion/models/gpt-5_1")
    print(f"System: You are a helpful Python programming assistant.")
    print(f"User: How do I check if a Python object is an instance of a class?")
    print(f"Max tokens: 512")
    print(f"Temperature: 0.7")
    print(f"Stream: False")
    print(f"{'='*60}\n")
    
    # Initialize OpenAI client using Clarifai's OpenAI-compatible endpoint
    client = OpenAI(
        base_url="https://api.clarifai.com/v2/ext/openai/v1",
        api_key=os.environ["CLARIFAI_PAT"],
    )
    
    response = client.chat.completions.create(
        model="openai/chat-completion/models/gpt-5_1",
        messages=[
            {"role": "system", "content": "You are a helpful Python programming assistant."},
            {
                "role": "user",
                "content": "How do I check if a Python object is an instance of a class?",
            },
        ],
        temperature=0.7,
        stream=False,
        max_tokens=512
    )
    
    # Output the result
    content = response.choices[0].message.content
    
    # Assert
    assert content is not None, "Response content should not be None"
    assert len(content) > 0, "Description should contain text"
    assert "isinstance" in content.lower() or "instance" in content.lower(), \
        "Response should mention isinstance or instance checking"
    
    print(f"\n{'='*60}")
    print(f"Test 5: Inference Result (GPT-5.1)")
    print(f"{'='*60}")
    print(f"Model: {response.model}")
    print(f"\nOutput:\n{content}")
    if response.usage:
        print(f"\nUsage:")
        print(f"  Prompt tokens: {response.usage.prompt_tokens}")
        print(f"  Completion tokens: {response.usage.completion_tokens}")
        print(f"  Total tokens: {response.usage.total_tokens}")
    print(f"{'='*60}\n")
