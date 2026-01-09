"""Pydantic models describing inference payloads."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.services import model_config

try:
    _configured_defaults = model_config.get_configured_models()
    DEFAULT_MODEL_IDS = [_configured_defaults[0].key] if _configured_defaults else ["general-image-recognition"]
except model_config.ModelConfigError:
    DEFAULT_MODEL_IDS = ["general-image-recognition"]


class InferenceParams(BaseModel):
    fps: float = Field(1.0, gt=0, le=10)
    min_confidence: float = Field(0.2, ge=0.0, le=1.0)
    max_concepts: int = Field(5, ge=1, le=20)
    batch_size: int = Field(8, ge=1, le=64)


class InferenceRequest(BaseModel):
    model_ids: List[str] = Field(default_factory=lambda: list(DEFAULT_MODEL_IDS))
    params: InferenceParams = Field(default_factory=InferenceParams)
    note: Optional[str] = None
    clip_id: Optional[str] = None
    model_config = {"protected_namespaces": ()}

    @field_validator("model_ids", mode="before")
    def ensure_model_ids(cls, value):
        if value is None or (isinstance(value, list) and not value):
            return list(DEFAULT_MODEL_IDS)
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("model_ids", mode="after")
    def resolve_model_ids(cls, values):
        resolved: list[str] = []
        for item in values:
            resolved.append(model_config.resolve_model_identifier(item))
        return resolved

    @field_validator("clip_id", mode="before")
    def normalize_clip_id(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return str(value)
