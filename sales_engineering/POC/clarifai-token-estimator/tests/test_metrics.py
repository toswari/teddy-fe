"""Tests for metrics helpers."""

from __future__ import annotations

from types import SimpleNamespace

from clarifai_token_estimator import metrics
from clarifai_token_estimator.metrics import build_metrics, estimate_token_count


def test_build_metrics_uses_usage_fields() -> None:
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    result = build_metrics(usage, "hello", "world", "dummy", ttft_ms=120.0, total_time_ms=340.0)
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15
    assert result.ttft_ms == 120.0
    assert result.total_time_ms == 340.0
    assert result.estimated is False


def test_build_metrics_estimates_when_usage_missing(monkeypatch) -> None:
    monkeypatch.setattr(metrics, "tiktoken", None)
    result = build_metrics(None, "hello world", "response", model=None, ttft_ms=None, total_time_ms=None)
    assert result.prompt_tokens > 0
    assert result.completion_tokens > 0
    assert result.total_tokens == result.prompt_tokens + result.completion_tokens
    assert result.estimated is True


def test_estimate_token_count_handles_empty(monkeypatch) -> None:
    monkeypatch.setattr(metrics, "tiktoken", None)
    assert estimate_token_count("", model=None) == 0
    assert estimate_token_count("abcd", model=None) > 0
