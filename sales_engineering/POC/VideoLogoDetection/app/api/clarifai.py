"""Clarifai helper API endpoints."""
from __future__ import annotations

from flask import Blueprint, request

from app.services.clarifai_catalog import ClarifaiCatalogError, list_models as list_catalog_models

bp = Blueprint("clarifai", __name__, url_prefix="/api/clarifai")


@bp.get("/models")
def list_models():
    """Return Clarifai models accessible to the configured PAT."""
    query = request.args.get("q") or request.args.get("query")
    per_page_raw = request.args.get("per_page")
    per_page = None
    if per_page_raw is not None:
        try:
            per_page = int(per_page_raw)
        except ValueError:
            per_page = None
    per_page = per_page or 25

    try:
        models = list_catalog_models(query=query, per_page=per_page)
    except ClarifaiCatalogError as exc:
        return {"error": str(exc)}, 503

    return {
        "count": len(models),
        "models": [model.__dict__ for model in models],
    }