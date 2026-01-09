"""Helpers for loading Clarifai model presets from config/models.yaml."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

MODEL_CONFIG_ENV_VAR = "MODEL_CONFIG_PATH"
DEFAULT_MODEL_CONFIG_PATH = "config/models.yaml"


class ModelConfigError(RuntimeError):
    """Raised when the Clarifai model config cannot be loaded."""


@dataclass
class ConfiguredModel:
    key: str
    name: str
    id: str
    version_id: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

    def serialize(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["model_id"] = payload.pop("id")
        payload["model_version_id"] = payload.pop("version_id")
        return payload


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_path(path: Optional[str] = None) -> Path:
    candidate = path or os.getenv(MODEL_CONFIG_ENV_VAR) or DEFAULT_MODEL_CONFIG_PATH
    resolved = Path(candidate)
    if not resolved.is_absolute():
        resolved = _project_root() / resolved
    return resolved


def _parse_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ModelConfigError(f"Model config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() in {".yml", ".yaml"}:
            data = yaml.safe_load(handle) or {}
        else:
            data = json.load(handle)
    if not isinstance(data, dict):
        raise ModelConfigError("Model config file must contain a mapping with a 'models' list")
    return data


def _validate_models(raw: Any) -> List[ConfiguredModel]:
    if not isinstance(raw, list):
        raise ModelConfigError("Model config must contain a list of models")
    models: List[ConfiguredModel] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ModelConfigError("Each model entry must be a mapping")
        for required in ("key", "name", "id"):
            if not entry.get(required):
                raise ModelConfigError(f"Model entry missing required field '{required}'")
        params = entry.get("params") or None
        if params is not None and not isinstance(params, dict):
            raise ModelConfigError("Model params must be a mapping if provided")
        models.append(
            ConfiguredModel(
                key=str(entry["key"]),
                name=str(entry["name"]),
                id=str(entry["id"]),
                version_id=str(entry["version_id"]) if entry.get("version_id") else None,
                params=params,
            )
        )
    return models


@lru_cache(maxsize=1)
def load_model_config(path: Optional[str] = None) -> List[ConfiguredModel]:
    config_path = _resolve_path(path)
    payload = _parse_file(config_path)
    models = _validate_models(payload.get("models"))
    if not models:
        raise ModelConfigError("Model config contains no models")
    return models


def reset_model_config_cache() -> None:
    load_model_config.cache_clear()  # type: ignore[attr-defined]


def get_configured_models() -> List[ConfiguredModel]:
    return load_model_config()


def get_model_by_key(key: str) -> Optional[ConfiguredModel]:
    key_lower = key.lower()
    for model in get_configured_models():
        if model.key.lower() == key_lower or model.name.lower() == key_lower:
            return model
    return None


def resolve_model_identifier(value: str) -> str:
    if not value:
        return value
    model = get_model_by_key(value)
    if model:
        return model.id
    return value


def serialize_configured_models() -> List[Dict[str, Any]]:
    return [model.serialize() for model in get_configured_models()]
