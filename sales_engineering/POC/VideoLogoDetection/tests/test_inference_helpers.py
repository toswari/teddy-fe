"""Tests for inference helper retry logic."""
from __future__ import annotations

from app.services.inference_service import FrameSample, run_single_model_inference, run_multi_model_inference


def test_run_single_model_retries(monkeypatch):
    frames = [FrameSample(index=0, timestamp_seconds=0.0, payload=b"a")] 
    calls = {"count": 0}

    def fake_run_models(self, frames_arg, model_ids, params):
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("transient")
        return [{"frame_index": 0, "model_id": model_ids[0], "label": "x", "confidence": 0.9}]

    monkeypatch.setattr("app.services.inference_service.ClarifaiClient.run_models", fake_run_models)

    results = run_single_model_inference(frames, "m1", params=type("P", (), {"max_concepts": 5, "min_confidence": 0.1, "batch_size": 1}))
    assert results and results[0]["model_id"] == "m1"


def test_run_multi_model_runs_each(monkeypatch):
    frames = [FrameSample(index=0, timestamp_seconds=0.0, payload=b"a")] 
    seen = []

    def fake_run_models(self, frames_arg, model_ids, params):
        mid = model_ids[0]
        seen.append(mid)
        return [{"frame_index": 0, "model_id": mid, "label": f"{mid}", "confidence": 0.8}]

    monkeypatch.setattr("app.services.inference_service.ClarifaiClient.run_models", fake_run_models)

    results = run_multi_model_inference(frames, ["mA", "mB"], params=type("P", (), {"max_concepts": 5, "min_confidence": 0.1, "batch_size": 1}))
    assert len(results) == 2
    assert set(seen) == {"mA", "mB"}
