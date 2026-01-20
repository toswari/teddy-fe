"""Example script that calls Gemini 2.5 Pro via the generate() streaming API."""

from __future__ import annotations

import os
from pathlib import Path

from clarifai_token_estimator.gemini_generate import (
    DEFAULT_GEMINI_MODEL_URL,
    GeminiGenerateClient,
)


def main() -> None:
    pat = os.environ.get("CLARIFAI_PAT")
    if not pat:
        raise SystemExit("CLARIFAI_PAT environment variable is required")

    generator = GeminiGenerateClient(pat=pat, model_url=DEFAULT_GEMINI_MODEL_URL)
    image_path = Path(__file__).resolve().parent.parent / "sample.png"
    if not image_path.exists():
        raise SystemExit(f"Sample image not found at {image_path}")
    image_size_bytes = image_path.stat().st_size
    image_size_mb = image_size_bytes / (1024 * 1024)

    result = generator.generate(
        prompt="Describe this image.",
        image_bytes=image_path.read_bytes(),
        max_tokens=512,
        temperature=0.5,
    )

    print("Gemini 2.5 Pro generate() demo")
    print(f"Model: {result.model_url}")
    print(f"Chunks: {result.chunk_count}")
    print(f"TTFT (ms): {result.ttft_ms or 'n/a'}")
    print(f"Total time (ms): {result.total_time_ms:.2f}")
    if result.usage:
        print(
            "Estimated tokens: "
            f"prompt={result.usage['prompt_tokens']} | "
            f"completion={result.usage['completion_tokens']} | "
            f"total={result.usage['total_tokens']}"
        )
    print(
        f"Image source: {image_path} "
        f"({image_size_bytes} bytes / {image_size_mb:.2f} MB)"
    )
    print("\nOutput:\n")
    print(result.text)


if __name__ == "__main__":
    main()