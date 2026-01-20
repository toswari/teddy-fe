#!/usr/bin/env python3
"""Utility script to send a multimodal prompt (text + image) to Clarifai."""

from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path
from typing import Optional

import requests

from clarifai_token_estimator.clarifai_client import ClarifaiOpenAIClient, GenerationParams
from clarifai_token_estimator.metrics import build_metrics

DEFAULT_BASE_URL = "https://api.clarifai.com/v2/ext/openai/v1"
DEFAULT_MODEL_URL = "openai/chat-completion/models/gpt-4o"
DEFAULT_PROMPT = "Describe what you see in this image. Highlight colors, objects, and notable context."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a multimodal prompt to Clarifai.")
    parser.add_argument("--model-url", default=DEFAULT_MODEL_URL, help="Full Clarifai model URL to call.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Text prompt to send alongside the image.")
    parser.add_argument("--image-path", help="Local path to an image file (png/jpg/webp/gif).")
    parser.add_argument("--image-url", help="HTTP URL to download an image for inference.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Clarifai OpenAI-compatible base URL.")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument(
        "--max-completion-tokens",
        "--max-tokens",
        dest="max_completion_tokens",
        type=int,
        default=512,
        help="Maximum completion tokens to request.",
    )
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--presence-penalty", type=float, default=0.0)
    parser.add_argument("--frequency-penalty", type=float, default=0.0)
    parser.add_argument("--no-stream", action="store_true", help="Send a non-streaming request.")
    return parser.parse_args()


def _data_url_from_path(path: str) -> str:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise SystemExit(f"Image path not found: {file_path}")
    mime_type = mimetypes.guess_type(file_path.name)[0] or "image/png"
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _data_url_from_http(image_url: str) -> str:
    try:
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as error:
        raise SystemExit(f"Unable to download image: {error}") from error
    mime_type = response.headers.get("Content-Type") or mimetypes.guess_type(image_url)[0] or "image/jpeg"
    encoded = base64.b64encode(response.content).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _resolve_image_data(path: Optional[str], url: Optional[str]) -> str:
    sources = [bool(path), bool(url)]
    if sum(sources) != 1:
        raise SystemExit("Provide exactly one of --image-path or --image-url.")
    if path:
        return _data_url_from_path(path)
    return _data_url_from_http(url or "")


def main() -> None:
    args = parse_args()

    api_key = os.environ.get("CLARIFAI_PAT")
    if not api_key:
        raise SystemExit("Set CLARIFAI_PAT in your environment before running this script.")

    image_data_url = _resolve_image_data(args.image_path, args.image_url)

    params = GenerationParams(
        temperature=args.temperature,
        max_completion_tokens=args.max_completion_tokens,
        top_p=args.top_p,
        presence_penalty=args.presence_penalty,
        frequency_penalty=args.frequency_penalty,
        stream=not args.no_stream,
    )

    try:
        client = ClarifaiOpenAIClient(api_key=api_key, base_url=args.base_url)
    except Exception as error:  # noqa: BLE001
        raise SystemExit(f"Failed to initialize Clarifai client: {error}") from error

    fragments: list[str] = []

    def _on_chunk(delta: str) -> None:
        fragments.append(delta)
        print(delta, end="", flush=True)

    result = client.stream_chat_completion(
        model=args.model_url,
        prompt=args.prompt,
        params=params,
        on_text_chunk=_on_chunk if params.stream else None,
        image_data=image_data_url,
    )

    if not params.stream:
        print(result.text)

    metrics = build_metrics(result.usage, args.prompt, result.text, args.model_url, result.ttft_ms, result.total_time_ms)

    print("\n--- Metrics ---")
    print(f"Input tokens: {metrics.prompt_tokens or 'n/a'}")
    print(f"Output tokens: {metrics.completion_tokens or 'n/a'}")
    print(f"TTFT (ms): {metrics.ttft_ms:.0f}" if metrics.ttft_ms is not None else "TTFT (ms): n/a")
    print(f"Total time (ms): {metrics.total_time_ms:.0f}" if metrics.total_time_ms is not None else "Total time (ms): n/a")
    if metrics.estimated:
        print("Token counts estimated locally; Clarifai usage data was unavailable.")


if __name__ == "__main__":
    main()
