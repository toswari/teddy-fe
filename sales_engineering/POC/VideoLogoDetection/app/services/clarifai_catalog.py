"""Clarifai model catalog helpers."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.clarifai.com"
MAX_PER_PAGE = 200


class ClarifaiCatalogError(RuntimeError):
    """Raised when Clarifai model discovery fails."""


@dataclass(frozen=True)
class ClarifaiModel:
    """Normalized Clarifai model descriptor returned to callers."""

    id: str
    name: str
    model_type: Optional[str]
    description: Optional[str]
    user_id: Optional[str]
    app_id: Optional[str]
    visibility: Optional[str]
    created_at: Optional[str]
    modified_at: Optional[str]
    workspace_id: Optional[str]
    url: Optional[str]
    tags: List[str]

    @classmethod
    def from_raw(
        cls,
        model: Dict[str, Any],
        fallback_user: Optional[str],
        fallback_app: Optional[str],
    ) -> "ClarifaiModel":
        user_id = model.get("user_id") or fallback_user
        app_id = model.get("app_id") or fallback_app
        model_id = model.get("id") or ""
        if not model_id:
            raise ClarifaiCatalogError("Encountered Clarifai model without an id")
        display_name = (model.get("display_name") or model.get("name") or model_id).strip()
        description = (model.get("description") or "").strip() or None
        visibility = None
        visibility_obj = model.get("visibility")
        if isinstance(visibility_obj, dict):
            visibility = visibility_obj.get("gettable") or visibility_obj.get("level")
        url = None
        if user_id and app_id:
            url = f"https://clarifai.com/{user_id}/{app_id}/models/{model_id}"
        tags: List[str] = []
        raw_tags = model.get("tags")
        if isinstance(raw_tags, list):
            tags = [str(tag) for tag in raw_tags]
        return cls(
            id=model_id,
            name=display_name,
            model_type=model.get("model_type_id"),
            description=description,
            user_id=user_id,
            app_id=app_id,
            visibility=visibility,
            created_at=model.get("created_at"),
            modified_at=model.get("modified_at") or model.get("updated_at"),
            workspace_id=model.get("workspace_id"),
            url=url,
            tags=tags,
        )


def _resolve_base_url() -> str:
    base = os.getenv("CLARIFAI_API_BASE", DEFAULT_BASE_URL).rstrip("/")
    if not base:
        return DEFAULT_BASE_URL
    return base


def _auth_headers(pat: str, user_id: Optional[str], app_id: Optional[str]) -> Dict[str, str]:
    headers = {
        "Authorization": f"Key {pat}",
    }
    if user_id:
        headers["X-Clarifai-User-Id"] = user_id
    if app_id:
        headers["X-Clarifai-App-Id"] = app_id
    return headers


def list_models(
    *,
    query: Optional[str] = None,
    per_page: int = 30,
    user_id: Optional[str] = None,
    app_id: Optional[str] = None,
) -> List[ClarifaiModel]:
    """Return a list of Clarifai models visible to the configured PAT."""

    pat = os.getenv("CLARIFAI_PAT")
    if not pat:
        raise ClarifaiCatalogError("CLARIFAI_PAT is not configured; cannot list Clarifai models")

    # Only use user/app path if explicitly requested, not from env vars
    # This allows listing public models by default
    base_url = _resolve_base_url()
    if user_id and app_id:
        url = f"{base_url}/v2/users/{user_id}/apps/{app_id}/models"
    else:
        # Use public models endpoint
        url = f"{base_url}/v2/models"

    params: Dict[str, Any] = {
        "per_page": max(1, min(per_page, MAX_PER_PAGE)),
    }
    if query:
        params["query"] = query

    try:
        response = requests.get(
            url,
            headers=_auth_headers(pat, user_id, app_id),
            params=params,
            timeout=15,
        )
    except requests.RequestException as exc:  # pragma: no cover - network failures
        logger.error("Clarifai model listing failed: %s", exc)
        raise ClarifaiCatalogError("Unable to reach Clarifai API") from exc

    if response.status_code == 401:
        raise ClarifaiCatalogError("Clarifai authentication failed; check CLARIFAI_PAT")
    if response.status_code >= 400:
        logger.error(
            "Clarifai API error (status=%s, body=%s)",
            response.status_code,
            response.text,
        )
        raise ClarifaiCatalogError("Clarifai API returned an error")

    payload = response.json() if response.content else {}
    raw_models = payload.get("models")
    if not isinstance(raw_models, list):
        logger.debug("Clarifai API response missing models array: %s", payload)
        raw_models = []

    normalized: List[ClarifaiModel] = []
    for model in raw_models:
        if not isinstance(model, dict):
            continue
        try:
            normalized.append(ClarifaiModel.from_raw(model, user_id, app_id))
        except ClarifaiCatalogError as exc:
            logger.debug("Skipping malformed Clarifai model entry: %s", exc)
            continue

    return normalized
