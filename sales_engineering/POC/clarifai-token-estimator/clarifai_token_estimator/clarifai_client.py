"""Clarifai OpenAI-compatible client helpers with streaming support."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

import requests

try:
    from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
except ImportError as exc:
    raise RuntimeError("openai package is required for Clarifai client") from exc


LOGGER = logging.getLogger(__name__)
MAX_DEBUG_TEXT = 500


@dataclass
class GenerationParams:
    """Parameters forwarded to the completion endpoint."""

    temperature: float = 0.7
    max_completion_tokens: Optional[int] = None
    top_p: float = 1.0
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stream: bool = True

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": self.stream,
        }
        # Use max_tokens as per Clarifai example
        if self.max_completion_tokens is not None:
            payload["max_tokens"] = self.max_completion_tokens
        if self.presence_penalty is not None:
            payload["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            payload["frequency_penalty"] = self.frequency_penalty
        return payload


@dataclass
class CompletionResult:
    """Result bundle from a completion request."""

    text: str
    usage: Any
    ttft_ms: Optional[float]
    total_time_ms: Optional[float]
    diagnostics: Dict[str, Any]
    debug: Dict[str, Any]


class ClarifaiOpenAIClient:
    """Wrapper around the OpenAI client configured for Clarifai's endpoint."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout: int = 60,
        request_timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("Clarifai API key is required")
        if not base_url:
            raise ValueError("Clarifai base URL is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.request_timeout = request_timeout
        self.max_retries = max(1, max_retries)
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """Return Clarifai models available via OpenAI compatibility."""

        try:
            page = self._client.models.list()
        except (APIConnectionError, APIStatusError, RateLimitError, requests.RequestException) as error:
            raise RuntimeError(f"Failed to list Clarifai models: {error}") from error
        models: List[Dict[str, Any]] = []
        for model in getattr(page, "data", []):
            models.append(
                {
                    "id": getattr(model, "id", None),
                    "owned_by": getattr(model, "owned_by", None),
                    "created": getattr(model, "created", None),
                }
            )
        if not models and hasattr(page, "model_dump"):
            payload = page.model_dump()
            for item in payload.get("data", []):
                models.append(
                    {
                        "id": item.get("id"),
                        "owned_by": item.get("owned_by"),
                        "created": item.get("created"),
                    }
                )
        return [model for model in models if model.get("id")]

    def stream_chat_completion(
        self,
        *,
        model: str,
        prompt: str,
        params: GenerationParams,
        on_text_chunk: Optional[Callable[[str], None]] = None,
        image_data: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> CompletionResult:
        """Stream a chat completion while measuring TTFT and total time."""

        if not model:
            raise ValueError("model is required")
        if not prompt:
            raise ValueError("prompt is required")

        attempt = 0
        error: Optional[Exception] = None
        while attempt < self.max_retries:
            attempt += 1
            try:
                return self._stream_once(
                    model=model,
                    prompt=prompt,
                    params=params,
                    on_text_chunk=on_text_chunk,
                    attempt=attempt,
                    image_data=image_data,
                    system_prompt=system_prompt,
                )
            except Exception as exc:  # noqa: BLE001
                error = exc
                if not self._should_retry(exc) or attempt >= self.max_retries:
                    raise
                backoff = self._backoff_seconds(attempt)
                time.sleep(backoff)
        if error:
            raise error
        raise RuntimeError("Unable to execute Clarifai completion")

    def _stream_once(
        self,
        *,
        model: str,
        prompt: str,
        params: GenerationParams,
        on_text_chunk: Optional[Callable[[str], None]],
        attempt: int,
        image_data: Optional[str],
        system_prompt: Optional[str],
    ) -> CompletionResult:
        start_time = time.perf_counter()
        chunks: List[str] = []
        usage: Any = None
        finish_reason: Optional[str] = None
        response_id: Optional[str] = None

        content_blocks: List[Dict[str, Any]] = []
        if prompt:
            content_blocks.append({"type": "text", "text": prompt})
        if image_data:
            content_blocks.append({"type": "image_url", "image_url": {"url": image_data}})
        if not content_blocks:
            raise ValueError("At least one of prompt or image_data must be provided")
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content_blocks})

        debug_request = {
            "model": model,
            "prompt": prompt[:MAX_DEBUG_TEXT] if prompt else None,
            "system_prompt": system_prompt[:MAX_DEBUG_TEXT] if system_prompt else None,
            "has_image": bool(image_data),
            "image_preview": image_data[:80] + "..." if image_data else None,
            "temperature": params.temperature,
            "max_completion_tokens": params.max_completion_tokens,
            "top_p": params.top_p,
            "presence_penalty": params.presence_penalty,
            "frequency_penalty": params.frequency_penalty,
            "stream": params.stream,
            "base_url": self.base_url,
            "api_key_prefix": self.api_key[:10] + "..." if self.api_key else None,
            "attempt": attempt,
        }
        self._log_debug("clarifai.request", debug_request)

        payload = params.to_payload()
        stream_mode = payload.pop("stream", True)
        # Follow Clarifai OpenAI-compatible example pattern
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream_mode,
            timeout=self.request_timeout,
            **payload,
        )

        usage: Any = None
        finish_reason: Optional[str] = None
        response_id: Optional[str] = None
        first_holder: List[Optional[float]] = [None]

        if not stream_mode:
            final = response
            text_content = self._extract_message_content(final)
            chunks.append(text_content)
            usage = getattr(final, "usage", None)
            finish_reason = self._extract_finish_reason(final)
            response_id = getattr(final, "id", None)
        else:
            stream_obj = response
            iterator: Iterable[Any]
            context_manager = getattr(stream_obj, "__enter__", None)
            if callable(context_manager):
                with stream_obj as managed_stream:  # type: ignore[assignment]
                    iterator = managed_stream
                    usage, finish_reason, response_id = self._consume_stream(
                        iterator,
                        chunks,
                        on_text_chunk,
                        first_token_holder=first_holder,
                    )
                    if hasattr(managed_stream, "get_final_response"):
                        final = managed_stream.get_final_response()
                        usage = getattr(final, "usage", usage)
                        finish_reason = finish_reason or self._extract_finish_reason(final)
                        response_id = response_id or getattr(final, "id", None)
            else:
                iterator = stream_obj
                usage, finish_reason, response_id = self._consume_stream(
                    iterator,
                    chunks,
                    on_text_chunk,
                    first_token_holder=first_holder,
                )
                response_obj = getattr(stream_obj, "response", None)
                if response_obj is not None:
                    usage = getattr(response_obj, "usage", usage)
                    finish_reason = finish_reason or self._extract_finish_reason(response_obj)
                    response_id = response_id or getattr(response_obj, "id", None)

        first_token_time: Optional[float] = first_holder[0]
        final_text = "".join(chunks)
        end_time = time.perf_counter()
        ttft_ms: Optional[float]
        if chunks and first_token_time is not None:
            ttft_ms = (first_token_time - start_time) * 1000
        else:
            ttft_ms = None
        total_time_ms = (end_time - start_time) * 1000

        diagnostics = {
            "attempt": attempt,
            "finish_reason": finish_reason,
            "response_id": response_id,
            "model": model,
            "base_url": self.base_url,
        }

        debug_response = {
            "text": final_text[:MAX_DEBUG_TEXT],
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
                "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
            } if usage else None,
            "finish_reason": finish_reason,
            "response_id": response_id,
            "ttft_ms": ttft_ms,
            "total_time_ms": total_time_ms,
        }

        self._log_debug("clarifai.response", debug_response)

        return CompletionResult(
            text=final_text,
            usage=usage,
            ttft_ms=ttft_ms,
            total_time_ms=total_time_ms,
            diagnostics=diagnostics,
            debug={"request": debug_request, "response": debug_response},
        )

    def _consume_stream(
        self,
        iterator: Iterable[Any],
        chunks: List[str],
        on_text_chunk: Optional[Callable[[str], None]],
        *,
        first_token_holder: List[Optional[float]],
    ) -> tuple[Any, Optional[str], Optional[str]]:
        usage: Any = None
        finish_reason: Optional[str] = None
        response_id: Optional[str] = None
        for item in iterator:
            choice = None
            if hasattr(item, "choices"):
                choices = getattr(item, "choices")
                if choices:
                    choice = choices[0]
            elif isinstance(item, dict):
                data_choices = item.get("choices")
                if data_choices:
                    choice = data_choices[0]
                    usage = item.get("usage", usage)
                    response_id = item.get("id", response_id)
            if choice is not None:
                delta = getattr(choice, "delta", None)
                if delta is None and isinstance(choice, dict):
                    delta = choice.get("delta")
                text_delta = None
                if delta is not None:
                    text_delta = getattr(delta, "content", None)
                    if text_delta is None and isinstance(delta, dict):
                        text_delta = delta.get("content")
                normalized_text = self._extract_text_from_content(text_delta)
                if normalized_text:
                    chunks.append(normalized_text)
                    if on_text_chunk:
                        on_text_chunk(normalized_text)
                    if first_token_holder[0] is None:
                        first_token_holder[0] = time.perf_counter()
                finish = getattr(choice, "finish_reason", None)
                if finish is None and isinstance(choice, dict):
                    finish = choice.get("finish_reason")
                if finish:
                    finish_reason = finish
            if getattr(item, "usage", None) and usage is None:
                usage = item.usage
            if getattr(item, "id", None) and response_id is None:
                response_id = item.id
        return usage, finish_reason, response_id

    @staticmethod
    def _log_debug(label: str, payload: Dict[str, Any]) -> None:
        """Safely emit debug payloads to logger and stdout."""

        try:
            message = json.dumps(payload, default=str)
        except (TypeError, ValueError):
            message = str(payload)
        LOGGER.debug("%s %s", label, message)
        print(f"{label}: {message}")

    @staticmethod
    def _extract_finish_reason(response: Any) -> Optional[str]:
        choices = getattr(response, "choices", None)
        if choices:
            first = choices[0]
            return getattr(first, "finish_reason", None)
        if isinstance(response, dict):
            data = response.get("choices")
            if data:
                return data[0].get("finish_reason")
        return None

    @staticmethod
    def _extract_message_content(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if choices:
            first = choices[0]
            message = getattr(first, "message", None)
            if message is not None:
                content = getattr(message, "content", None)
                text = ClarifaiOpenAIClient._extract_text_from_content(content)
                if text:
                    return text
            delta = getattr(first, "delta", None)
            if delta is not None:
                content = getattr(delta, "content", None)
                text = ClarifaiOpenAIClient._extract_text_from_content(content)
                if text:
                    return text
        if isinstance(response, dict):
            data = response.get("choices")
            if data:
                first = data[0]
                message = first.get("message") if isinstance(first, dict) else None
                if isinstance(message, dict):
                    content = message.get("content")
                    text = ClarifaiOpenAIClient._extract_text_from_content(content)
                    if text:
                        return text
        return ""

    @staticmethod
    def _extract_text_from_content(content: Any) -> str:
        if not content:
            return ""

        collected: List[str] = []

        def _collect(node: Any) -> None:
            if node is None:
                return
            if isinstance(node, str):
                collected.append(node)
                return
            if isinstance(node, list):
                for item in node:
                    _collect(item)
                return
            if isinstance(node, dict):
                node_type = node.get("type")
                if isinstance(node_type, str) and "image" in node_type:
                    return
                for key in ("text", "content", "parts", "value"):
                    if key in node:
                        _collect(node[key])
                if not any(key in node for key in ("text", "content", "parts", "value")):
                    for key, value in node.items():
                        if key == "type":
                            continue
                        if isinstance(value, (dict, list)):
                            _collect(value)

        _collect(content)
        return "".join(collected)

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError):
            return exc.status_code >= 500
        if isinstance(exc, APIConnectionError):
            return True
        if isinstance(exc, requests.Timeout):
            return True
        return False

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        return min(10.0, 2 ** attempt)
