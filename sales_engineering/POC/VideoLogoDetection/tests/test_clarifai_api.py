"""Tests for Clarifai model discovery endpoints."""
from __future__ import annotations

import json

def test_clarifai_models_requires_pat(client, monkeypatch):
    monkeypatch.delenv("CLARIFAI_PAT", raising=False)

    response = client.get("/api/clarifai/models")

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["error"].startswith("CLARIFAI_PAT")


def test_clarifai_models_success(client, monkeypatch):
    monkeypatch.setenv("CLARIFAI_PAT", "test-pat")
    monkeypatch.setenv("CLARIFAI_USER_ID", "demo")
    monkeypatch.setenv("CLARIFAI_APP_ID", "sandbox")

    models_payload = {
        "models": [
            {
                "id": "logo-detector",
                "name": "Logo Detector",
                "description": "Detects common logos",
                "model_type_id": "visual-detector",
                "created_at": "2023-01-01T00:00:00Z",
                "modified_at": "2023-01-02T00:00:00Z",
            }
        ]
    }

    class DummyResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload
            self.text = json.dumps(payload)
            self.content = self.text.encode("utf-8")

        def json(self):
            return self._payload

    def fake_get(url, headers=None, params=None, timeout=None):
        assert url.endswith("/v2/users/demo/apps/sandbox/models")
        assert headers["Authorization"].startswith("Key ")
        return DummyResponse(models_payload)

    monkeypatch.setattr("app.services.clarifai_catalog.requests.get", fake_get)

    response = client.get("/api/clarifai/models?per_page=10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["models"][0]["id"] == "logo-detector"
    assert payload["models"][0]["name"] == "Logo Detector"
    assert payload["models"][0]["model_type"] == "visual-detector"


def test_clarifai_models_config_endpoint(client, monkeypatch):
    expected_models = [
        {
            "key": "general",
            "name": "General Classification",
            "model_id": "general-image-recognition",
            "description": "Generic vision model",
        }
    ]
    monkeypatch.setattr(
        "app.api.clarifai.serialize_configured_models",
        lambda: expected_models,
    )

    response = client.get("/api/clarifai/models/config")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["models"] == expected_models