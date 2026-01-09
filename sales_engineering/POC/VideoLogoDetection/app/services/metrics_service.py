"""Metrics and benchmarking helpers."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Optional, Tuple
import time

from sqlalchemy.orm import selectinload

from app.models import InferenceRun

# Simple in-memory counters for observability
counters = defaultdict(int)
timers = defaultdict(list)

def increment_counter(name: str, value: int = 1):
    counters[name] += value

def record_timer(name: str, duration: float):
    timers[name].append(duration)

def get_counters():
    return dict(counters)

def get_timers():
    return {k: {"count": len(v), "avg": sum(v)/len(v) if v else 0} for k, v in timers.items()}


def project_metrics(project_id: int) -> Dict[str, dict]:
    """Aggregate detection metrics for a project across completed runs."""
    runs = (
        InferenceRun.query.options(selectinload(InferenceRun.detections))
        .filter_by(project_id=project_id, status="completed")
        .all()
    )

    model_summary: dict[str, dict] = defaultdict(
        lambda: {
            "detections": 0,
            "confidence_sum": 0.0,
            "frames": 0,
            "runs": set(),
            "cost_actual": 0.0,
            "cost_projected": 0.0,
            "processing_time": 0.0,
        }
    )

    for run in runs:
        frames_sampled = int((run.results or {}).get("frames_sampled", 0))
        processing_time_seconds = float((run.results or {}).get("processing_time_seconds") or 0.0)
        models_in_run = {det.model_id or "unknown" for det in run.detections}
        if not models_in_run:
            models_in_run = set((run.model_ids or ["unknown"]))

        split_count = max(len(models_in_run), 1)
        for model_id in models_in_run:
            entry = model_summary[model_id]
            entry["frames"] += frames_sampled
            entry["runs"].add(run.id)
            entry["cost_actual"] += float(run.cost_actual or 0.0) / split_count
            entry["cost_projected"] += float(run.cost_projected or 0.0) / split_count
            entry["processing_time"] += processing_time_seconds / split_count

        for detection in run.detections:
            model_id = detection.model_id or "unknown"
            entry = model_summary[model_id]
            entry["detections"] += 1
            entry["confidence_sum"] += float(detection.confidence or 0.0)

    metrics: dict[str, dict] = {}
    for model_id, data in model_summary.items():
        runs_count = max(len(data["runs"]), 1)
        frames = max(data["frames"], 1)
        detections = data["detections"]
        metrics[model_id] = {
            "detections": detections,
            "avg_confidence": round((data["confidence_sum"] / max(detections, 1)), 4),
            "detection_density": round(detections / frames, 4),
            "hit_frequency": round(detections / runs_count, 2),
            "cost_actual": round(data["cost_actual"], 4),
            "cost_projected": round(data["cost_projected"], 4),
            "frames_processed": data["frames"],
            "avg_processing_seconds": round(data["processing_time"] / runs_count, 2),
        }
    return metrics


def run_metrics(run_id: int) -> Optional[dict]:
    run = (
        InferenceRun.query.options(selectinload(InferenceRun.detections))
        .filter_by(id=run_id)
        .first()
    )
    if not run:
        return None

    detections_by_model: dict[str, int] = defaultdict(int)
    confidence_by_model: dict[str, float] = defaultdict(float)
    for detection in run.detections:
        key = detection.model_id or "unknown"
        detections_by_model[key] += 1
        confidence_by_model[key] += float(detection.confidence or 0.0)

    models = {}
    for model_id, count in detections_by_model.items():
        models[model_id] = {
            "detections": count,
            "avg_confidence": round(confidence_by_model[model_id] / max(count, 1), 4),
        }

    return {
        "run_id": run.id,
        "video_id": run.video_id,
        "status": run.status,
        "frames_sampled": (run.results or {}).get("frames_sampled", 0),
        "processing_time_seconds": float((run.results or {}).get("processing_time_seconds") or 0.0),
        "models": models,
        "cost_actual": float(run.cost_actual or 0.0),
        "cost_projected": float(run.cost_projected or 0.0),
        "efficiency_ratio": float(run.efficiency_ratio or 0.0),
    }


def summarize_run_models(run: InferenceRun) -> Tuple[list[str], dict[str, int]]:
    """Return ordered model identifiers plus detection counts for an inference run."""
    ordered_models: list[str] = []
    detection_counts: dict[str, int] = {}

    for model_id in run.model_ids or []:
        if model_id and model_id not in ordered_models:
            ordered_models.append(model_id)

    for detection in run.detections:
        key = detection.model_id or "unknown"
        detection_counts[key] = detection_counts.get(key, 0) + 1
        if key not in ordered_models:
            ordered_models.append(key)

    if not ordered_models:
        ordered_models = list(detection_counts.keys()) or ["unknown"]

    for model_id in ordered_models:
        detection_counts.setdefault(model_id, 0)

    return ordered_models, detection_counts
