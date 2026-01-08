"""Simple billing and cost estimation helpers."""
from __future__ import annotations

from typing import Iterable

from app.models import InferenceRun

# Reference pricing (placeholder values for MVP)
MODEL_COST_PER_FRAME = 0.0025
BASE_RUN_COST = 0.05


def estimate_project_cost(fps: float, model_ids: Iterable[str], duration_seconds: float) -> float:
    """Estimate project cost using a simple per-frame pricing model."""
    frames = max(int(duration_seconds * fps), 1)
    models = max(len(list(model_ids)), 1)
    return round(BASE_RUN_COST + (frames * models * MODEL_COST_PER_FRAME), 4)


def apply_run_cost(inference_run: InferenceRun, frames_sampled: int) -> None:
    """Populate projected and actual cost fields on an inference run."""
    models = max(len(inference_run.model_ids or []), 1)
    projected = BASE_RUN_COST + (frames_sampled * models * MODEL_COST_PER_FRAME)
    inference_run.cost_projected = round(projected, 4)
    inference_run.cost_actual = inference_run.cost_projected
    inference_run.efficiency_ratio = (
        len((inference_run.results or {}).get("detections", [])) / inference_run.cost_actual
        if inference_run.cost_actual
        else 0
    )
