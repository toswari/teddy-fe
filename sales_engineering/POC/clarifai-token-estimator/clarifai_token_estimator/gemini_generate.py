"""Helpers for calling Gemini 2.5 Pro via Clarifai's native SDK generate() flow."""

from __future__ import annotations

import base64
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence

from clarifai.client.model import Model
from clarifai.runners.utils.data_types import Image, Text
from .metrics import estimate_token_count

LOGGER = logging.getLogger(__name__)
DEFAULT_GEMINI_MODEL_URL = "https://clarifai.com/gcp/generate/models/gemini-2_5-pro"
IMAGE_TOKEN_MIN = 85
IMAGE_TOKEN_MAX = 4096
IMAGE_BYTES_PER_TOKEN = 1024  # rough heuristic: 1 KB ≈ 1 token
MAX_DEBUG_TEXT = 500


@dataclass
class GeminiGenerateResult:
    """Aggregated response from the Gemini generate() stream."""

    prompt: str
    text: str
    chunks: List[str]
    chunk_count: int
    ttft_ms: Optional[float]
    total_time_ms: float
    model_url: str
    usage: Optional[dict]
    image_tokens: int


class GeminiGenerateClient:
    """Thin wrapper that converts Gemini generate() streams into plain text results."""

    def __init__(self, pat: str, *, model_url: str = DEFAULT_GEMINI_MODEL_URL) -> None:
        if not pat:
            raise ValueError("Clarifai PAT is required to call Gemini")
        self.model_url = model_url
        self._model = Model(url=model_url, pat=pat)

    def generate(
        self,
        *,
        prompt: str,
        image_url: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_base64: Optional[str] = None,
        image: Optional[Image] = None,
        temperature: float = 0.5,
        top_p: float = 0.9,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        tools: Optional[Sequence[dict]] = None,
        tool_choice: Optional[str] = None,
        chat_history: Optional[Sequence[dict]] = None,
        estimate_tokens: bool = True,
    ) -> GeminiGenerateResult:
        if not prompt:
            raise ValueError("prompt is required for Gemini generate()")

        payload: dict = {
            "prompt": prompt,
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        if tools:
            payload["tools"] = list(tools)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if chat_history:
            payload["chat_history"] = list(chat_history)

        image_source = None
        if image is not None:
            image_source = "image_object"
        elif image_bytes is not None:
            image_source = "bytes"
        elif image_base64 is not None:
            image_source = "base64"
        elif image_url is not None:
            image_source = "url"

        image_input = image or self._build_image(image_url, image_base64, image_bytes)
        image_tokens = 0
        image_bytes_len: Optional[int] = None
        if image_input is not None:
            payload["image"] = image_input
            image_tokens = self._estimate_image_tokens(image_input)
            image_bytes_len = self._resolve_image_bytes_len(image_input)

        debug_request = {
            "model_url": self.model_url,
            "prompt": prompt[:MAX_DEBUG_TEXT],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
            "tool_count": len(tools) if tools else 0,
            "tool_choice": tool_choice,
            "chat_history_items": len(chat_history) if chat_history else 0,
            "has_image": image_input is not None,
            "image_source": image_source,
            "image_bytes": image_bytes_len,
            "image_tokens": image_tokens if image_input is not None else None,
        }
        self._log_debug("gemini.generate.request", debug_request)

        stream = self._invoke_generate(payload)
        result = self._collect_stream(prompt, stream, estimate_tokens, image_tokens)

        debug_response = {
            "model_url": self.model_url,
            "text": result.text[:MAX_DEBUG_TEXT],
            "chunk_count": result.chunk_count,
            "ttft_ms": result.ttft_ms,
            "total_time_ms": result.total_time_ms,
            "usage": result.usage,
            "image_tokens": result.image_tokens,
        }
        self._log_debug("gemini.generate.response", debug_response)

        return result

    def _invoke_generate(self, payload: dict) -> Iterator[object]:
        """Call model.generate() while handling the image/images signature toggle."""

        call_kwargs = dict(payload)
        try:
            return self._model.generate(**call_kwargs)
        except TypeError as error:
            if "unexpected keyword argument 'image'" in str(error) and "image" in call_kwargs:
                image_value = call_kwargs.pop("image")
                call_kwargs["images"] = [image_value]
                LOGGER.debug("Retrying Gemini generate() with images=list(Image)")
                return self._model.generate(**call_kwargs)
            raise

    def _collect_stream(
        self,
        prompt: str,
        stream: Iterable[object],
        estimate_tokens: bool,
        image_tokens: int,
    ) -> GeminiGenerateResult:
        chunks: List[str] = []
        start = time.perf_counter()
        first_chunk_at: Optional[float] = None

        for result in stream:
            text_chunk = self._extract_text(result)
            if text_chunk:
                if first_chunk_at is None:
                    first_chunk_at = time.perf_counter()
                chunks.append(text_chunk)

        total_time_ms = (time.perf_counter() - start) * 1000
        ttft_ms = (first_chunk_at - start) * 1000 if first_chunk_at is not None else None
        final_text = "".join(chunks).strip()

        if not final_text:
            raise RuntimeError("Gemini generate() returned no text chunks")

        usage = (
            self._estimate_usage(prompt, final_text, image_tokens)
            if estimate_tokens
            else None
        )

        return GeminiGenerateResult(
            prompt=prompt,
            text=final_text,
            chunks=chunks,
            chunk_count=len(chunks),
            ttft_ms=ttft_ms,
            total_time_ms=total_time_ms,
            model_url=self.model_url,
            usage=usage,
            image_tokens=image_tokens,
        )

    def _build_image(
        self,
        image_url: Optional[str],
        image_base64: Optional[str],
        image_bytes: Optional[bytes],
    ) -> Optional[Image]:
        if image_bytes:
            return Image(bytes=image_bytes)
        if image_base64:
            try:
                decoded = base64.b64decode(image_base64)
            except Exception as error:  # noqa: BLE001
                raise ValueError("Invalid base64 payload for image") from error
            return Image(bytes=decoded)
        if image_url:
            return Image(url=image_url)
        return None

    def _extract_text(
        self,
        result: object,
    ) -> str:
        return self._extract_text_from_result(result)

    @staticmethod
    def _extract_text_from_result(result: object) -> str:
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, Text):
            return result.text or ""
        if hasattr(result, "text") and isinstance(getattr(result, "text"), str):
            return getattr(result, "text")
        if isinstance(result, dict):
            for key in ("text", "content", "response", "value"):
                value = result.get(key)
                if isinstance(value, str) and value:
                    return value
                if isinstance(value, Text):
                    return value.text or ""
                if hasattr(value, "text") and isinstance(getattr(value, "text"), str):
                    return getattr(value, "text")
        if hasattr(result, "__dict__"):
            return GeminiGenerateClient._extract_text_from_result(vars(result))
        return str(result) if result else ""

    def _estimate_usage(self, prompt: str, completion: str, image_tokens: int) -> dict:
        prompt_tokens = estimate_token_count(prompt, self.model_url)
        prompt_tokens += image_tokens
        completion_tokens = estimate_token_count(completion, self.model_url)
        total_tokens = prompt_tokens + completion_tokens
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated": True,
        }

    @staticmethod
    def _resolve_image_bytes_len(image: Image) -> int:
        data = getattr(image, "bytes", None)
        if data:
            return len(data)
        return 0

    def _estimate_image_tokens(self, image: Image) -> int:
        byte_length = self._resolve_image_bytes_len(image)
        if byte_length:
            tokens = math.ceil(byte_length / IMAGE_BYTES_PER_TOKEN)
            return max(IMAGE_TOKEN_MIN, min(tokens, IMAGE_TOKEN_MAX))
        return IMAGE_TOKEN_MIN

    @staticmethod
    def _log_debug(label: str, payload: dict) -> None:
        try:
            message = json.dumps(payload, default=str)
        except (TypeError, ValueError):
            message = str(payload)
        LOGGER.debug("%s %s", label, message)
        print(f"{label}: {message}")
