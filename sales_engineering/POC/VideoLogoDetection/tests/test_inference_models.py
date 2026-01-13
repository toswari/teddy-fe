"""Tests for inference request schemas."""
from __future__ import annotations

from app.services.inference_models import InferenceRequest


def test_inference_request_defaults_to_configured_models(monkeypatch):
    monkeypatch.setattr("app.services.inference_models.DEFAULT_MODEL_IDS", ["logos"])
    monkeypatch.setattr(
        "app.services.inference_models.model_config.resolve_model_identifier",
        lambda value: value,
    )

    request = InferenceRequest()

    assert request.model_ids == ["logos"]


def test_inference_request_accepts_single_string(monkeypatch):
    resolved = {"logos": "logo-detection-v2"}
    monkeypatch.setattr(
        "app.services.inference_models.model_config.resolve_model_identifier",
        lambda value: resolved.get(value, value),
    )

    request = InferenceRequest(model_ids="logos")

    assert request.model_ids == ["logo-detection-v2"]


def test_inference_request_trims_clip_id(monkeypatch):
    monkeypatch.setattr(
        "app.services.inference_models.model_config.resolve_model_identifier",
        lambda value: value,
    )

    request = InferenceRequest(clip_id="  clip-123  ")

    assert request.clip_id == "clip-123"