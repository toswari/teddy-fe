"""Utility helpers for measuring Clarifai inference metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

try:
    import tiktoken  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None  # type: ignore

DEFAULT_MODEL_ENCODING = "cl100k_base"


@dataclass
class InferenceMetrics:
    """Container for inference metrics."""

    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    ttft_ms: Optional[float]
    total_time_ms: Optional[float]
    estimated: bool = False

    @property
    def to_dict(self) -> dict[str, Optional[float]]:
        """Return metrics as a serialisable dict."""

        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "ttft_ms": self.ttft_ms,
            "total_time_ms": self.total_time_ms,
            "estimated": self.estimated,
        }


def _resolve_encoding(model: Optional[str]) -> Any:
    if not tiktoken:
        return None
    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass
    return tiktoken.get_encoding(DEFAULT_MODEL_ENCODING)


def estimate_token_count(text: str, model: Optional[str] = None) -> int:
    """Estimate token count using tiktoken if available, else heuristic."""

    if not text:
        return 0
    encoding = _resolve_encoding(model)
    if encoding:
        return len(encoding.encode(text))
    return max(1, len(text) // 4)


def _usage_value(payload: Any, key: str) -> Optional[Any]:
    if payload is None:
        return None
    if hasattr(payload, key):
        return getattr(payload, key)
    if isinstance(payload, dict):
        return payload.get(key)
    return None


def build_metrics(
    usage: Optional[Any],
    prompt_text: str,
    completion_text: str,
    model: Optional[str],
    ttft_ms: Optional[float],
    total_time_ms: Optional[float],
) -> InferenceMetrics:
    """Construct metrics from API usage or local estimation."""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated = False

    usage_prompt = _usage_value(usage, "prompt_tokens")
    if usage and usage_prompt is not None:
        usage_completion = _usage_value(usage, "completion_tokens")
        usage_total = _usage_value(usage, "total_tokens")
        usage_estimated = _usage_value(usage, "estimated")
        prompt_tokens = int(usage_prompt)
        completion_tokens = int(usage_completion or 0)
        total_tokens = int(usage_total or (prompt_tokens + completion_tokens))
        estimated = bool(usage_estimated)
    else:
        prompt_tokens = estimate_token_count(prompt_text, model)
        completion_tokens = estimate_token_count(completion_text, model)
        total_tokens = prompt_tokens + completion_tokens
        estimated = True

    return InferenceMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        ttft_ms=ttft_ms,
        total_time_ms=total_time_ms,
        estimated=estimated,
    )
