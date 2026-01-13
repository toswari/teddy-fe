"""Vision-language model helper endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, request

from app.services.vlm_service import VLMServiceError, list_models, run_vlm_for_run

bp = Blueprint("vlm", __name__, url_prefix="/api/vlm")


@bp.get("/models")
def list_vlm_models():
    base_url = current_app.config.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    api_key = current_app.config.get("LMSTUDIO_API_KEY")
    try:
        models = list_models(base_url, api_key)
    except VLMServiceError as exc:
        return {"error": str(exc)}, 503
    return {"count": len(models), "models": models}


@bp.post("/run")
def trigger_vlm_run():
    payload = request.get_json(silent=True) or {}
    run_id = payload.get("runId")
    model_id = payload.get("modelId")
    limit_raw = payload.get("limit")

    if not isinstance(run_id, int):
        return {"error": "runId must be an integer"}, 400
    if not isinstance(model_id, str) or not model_id.strip():
        return {"error": "modelId is required"}, 400

    limit: int | None = None
    if limit_raw is not None:
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return {"error": "limit must be an integer"}, 400
        if limit < 1:
            return {"error": "limit must be >= 1"}, 400

    base_url = current_app.config.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    api_key = current_app.config.get("LMSTUDIO_API_KEY")

    try:
        result = run_vlm_for_run(
            run_id,
            model_id.strip(),
            limit,
            base_url=base_url,
            api_key=api_key,
        )
    except VLMServiceError as exc:
        current_app.logger.warning("VLM run failed: %s", exc)
        return {"error": str(exc)}, 400

    return result
