#!/usr/bin/env python3
"""Sample Clarifai OpenAI-compatible request for product photo inspection."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, List

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.clarifai.com/v2/ext/openai/v1"
DEFAULT_MODEL_URL = "https://clarifai.com/gcp/generate/models/gemini-2_5-pro"
DEFAULT_SYSTEM_MESSAGE = "You are a helpful assistant that inspects product photos."
DEFAULT_PROMPT = "Analyze the attached image and list 3 visual improvements."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a product photo review request to Clarifai.")
    parser.add_argument("--image-url", required=True, help="Publicly accessible image URL to analyze.")
    parser.add_argument("--model-url", default=DEFAULT_MODEL_URL, help="Clarifai model URL or slug.")
    parser.add_argument("--system", default=DEFAULT_SYSTEM_MESSAGE, help="System message for the assistant.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="User prompt describing the analysis task.")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature.")
    parser.add_argument(
        "--max-completion-tokens",
        "--max-tokens",
        dest="max_completion_tokens",
        type=int,
        default=512,
        help="Maximum completion tokens.",
    )
    return parser.parse_args()


def _flatten_content(content: Any) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "output_text" and isinstance(block.get("text"), list):
                    for item in block["text"]:
                        if isinstance(item, dict) and isinstance(item.get("text"), str):
                            parts.append(item["text"])
                elif block_type == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        return "".join(parts)
    return ""


def main() -> None:
    args = parse_args()

    api_key = os.environ.get("CLARIFAI_PAT")
    if not api_key:
        raise SystemExit("Set CLARIFAI_PAT before running this script.")

    client = OpenAI(api_key=api_key, base_url=DEFAULT_BASE_URL)

    messages = [
        {"role": "system", "content": args.system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": args.prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": args.image_url},
                },
            ],
        },
    ]

    try:
        response = client.chat.completions.create(
            model=args.model_url,
            messages=messages,
            temperature=args.temperature,
            max_tokens=args.max_completion_tokens,
        )
    except Exception as error:  # noqa: BLE001
        raise SystemExit(f"Clarifai request failed: {error}") from error

    choice = response.choices[0]
    content = getattr(choice.message, "content", None)
    text = _flatten_content(content)
    if not text and isinstance(content, str):
        text = content

    print("\nAssistant response:\n")
    print(text or "<no content returned>")


if __name__ == "__main__":
    main()
