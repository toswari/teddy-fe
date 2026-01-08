"""Metrics API blueprint."""
from __future__ import annotations

from flask import Blueprint

from app.services import metrics_service

bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


@bp.get("/projects/<int:project_id>")
def project_metrics(project_id: int):
    metrics = metrics_service.project_metrics(project_id)
    return {"project_id": project_id, "models": metrics}


@bp.get("/inference-runs/<int:run_id>")
def inference_run_metrics(run_id: int):
    metrics = metrics_service.run_metrics(run_id)
    if metrics is None:
        return {"error": "Inference run not found"}, 404
    return metrics
