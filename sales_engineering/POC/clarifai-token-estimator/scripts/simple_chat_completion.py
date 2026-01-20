#!/usr/bin/env python3
"""Minimal Clarifai OpenAI-compatible chat completion example."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from openai import OpenAI

DEFAULT_BASE_URL = "https://api.clarifai.com/v2/ext/openai/v1"
DEFAULT_MODEL = "openai/chat-completion/models/gpt-4o"
DEFAULT_SYSTEM = "You are a helpful assistant."
DEFAULT_PROMPT = "Who are you?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a simple chat completion request to Clarifai.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Clarifai model slug or full URL.")
    parser.add_argument("--system", default=DEFAULT_SYSTEM, help="System message content.")
    parser.add_argument("--user", default=DEFAULT_PROMPT, help="User prompt content.")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature.")
    parser.add_argument("--max-completion-tokens", type=int, default=100, help="Max completion tokens.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Clarifai OpenAI-compatible base URL.")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming; return one payload.")
    return parser.parse_args()


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join([part.get("text", "") for part in content if isinstance(part, dict)])
    return ""


def main() -> None:
    args = parse_args()

    api_key = os.environ.get("CLARIFAI_PAT")
    if not api_key:
        raise SystemExit("Set CLARIFAI_PAT before running this script.")

    client = OpenAI(api_key=api_key, base_url=args.base_url)
    messages = [
        {"role": "system", "content": args.system},
        {"role": "user", "content": args.user},
    ]

    stream = not args.no_stream

    response = client.chat.completions.create(
        model=args.model,
        messages=messages,
        max_tokens=args.max_completion_tokens,
        temperature=args.temperature,
        stream=stream,
    )

    if stream:
        print("Assistant response (stream):\n")
        for chunk in response:
            try:
                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                content = getattr(delta, "content", None)
                if content is None and isinstance(choice, dict):
                    content = choice.get("delta", {}).get("content")
                text = _extract_text(content)
                if text:
                    print(text, end="", flush=True)
            except Exception:  # noqa: BLE001
                continue
        print("\n")
    else:
        choice = response.choices[0]
        content = getattr(choice.message, "content", None)
        if content is None and isinstance(choice, dict):
            content = choice.get("message", {}).get("content")
        print("Assistant response:\n")
        print(_extract_text(content))


if __name__ == "__main__":
    main()
