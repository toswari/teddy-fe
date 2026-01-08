"""Pydantic models describing inference payloads."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, validator


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

    @validator("model_ids", pre=True)
    def ensure_model_ids(cls, value):
        if value is None or (isinstance(value, list) and not value):
            return list(DEFAULT_MODEL_IDS)
        if isinstance(value, str):
            return [value]
        return value
