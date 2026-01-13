"""Tests for Clarifai model config loader."""
from __future__ import annotations

import textwrap

import pytest

from app.services import model_config


@pytest.fixture(autouse=True)
def reset_config_cache():
    model_config.reset_model_config_cache()
    yield
    model_config.reset_model_config_cache()


def _write_config(tmp_path, content: str):
    path = tmp_path / "models.yaml"
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def test_load_model_config_from_yaml(tmp_path, monkeypatch):
    config_path = _write_config(
        tmp_path,
        """
        models:
          - key: general
            name: General
            id: general-image-recognition
          - key: logos
            name: Logos
            id: logo-detection-v2
        """,
    )
    monkeypatch.setenv("MODEL_CONFIG_PATH", str(config_path))

    models = model_config.get_configured_models()

    assert len(models) == 2
    assert models[0].key == "general"
    assert models[1].id == "logo-detection-v2"


def test_missing_model_config_raises(tmp_path, monkeypatch):
    missing = tmp_path / "missing.yaml"
    monkeypatch.setenv("MODEL_CONFIG_PATH", str(missing))

    with pytest.raises(model_config.ModelConfigError):
        model_config.get_configured_models()


def test_resolve_model_identifier_prefers_config(monkeypatch):
    dummy_models = [
        model_config.ConfiguredModel(key="general", name="General", id="general-image-recognition"),
        model_config.ConfiguredModel(key="logos", name="Logos", id="logo-detection-v2"),
    ]
    monkeypatch.setattr("app.services.model_config.get_configured_models", lambda: dummy_models)

    assert model_config.resolve_model_identifier("general") == "general-image-recognition"
    assert model_config.resolve_model_identifier("Logos") == "logo-detection-v2"
    assert model_config.resolve_model_identifier("custom-model") == "custom-model"
