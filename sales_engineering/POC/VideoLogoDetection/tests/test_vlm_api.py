from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict

import pytest

from app.extensions import db
from app.models import Detection, InferenceRun, Project, Video
from app.services.vlm_service import VLMServiceError, run_vlm_for_run


class _FakeResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.reason = "Error"

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_list_models_success(client, monkeypatch):
    payload = {
        "data": [
            {"id": "qwen/qwen2.5-vl-7b", "name": "Qwen2.5-VL 7B"},
            {"id": "zai-org/glm-4.6v-flash"},
        ]
    }

    def fake_get(url, headers=None, timeout=None):
        fake_get.called_with = {"url": url, "headers": headers, "timeout": timeout}
        return _FakeResponse(200, payload)

    monkeypatch.setattr("app.services.vlm_service.requests.get", fake_get)

    client.application.config["LMSTUDIO_BASE_URL"] = "http://localhost:1234/v1"
    client.application.config["LMSTUDIO_API_KEY"] = "token-value"

    response = client.get("/api/vlm/models")
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] == 2
    assert data["models"][0]["id"] == "qwen/qwen2.5-vl-7b"
    assert data["models"][0]["pinned"] is True
    assert data["models"][1]["id"] == "zai-org/glm-4.6v-flash"
    assert data["models"][1]["pinned"] is True
    assert fake_get.called_with["url"].endswith("/models")
    assert fake_get.called_with["headers"].get("Authorization") == "Bearer token-value"


def test_list_models_adds_missing_pinned(client, monkeypatch):
    payload = {
        "data": [
            {"id": "qwen/qwen2.5-vl-7b"},
        ]
    }

    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse(200, payload)

    monkeypatch.setattr("app.services.vlm_service.requests.get", fake_get)

    response = client.get("/api/vlm/models")
    data = response.get_json()

    assert response.status_code == 200
    model_ids = [model["id"] for model in data["models"]]
    assert "qwen/qwen2.5-vl-7b" in model_ids
    assert "zai-org/glm-4.6v-flash" in model_ids
    assert any(model["id"] == "zai-org/glm-4.6v-flash" and model.get("pinned") for model in data["models"])
    assert data["count"] == len(data["models"]) == 2


def test_list_models_failure(client, monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse(500, text="oops")

    monkeypatch.setattr("app.services.vlm_service.requests.get", fake_get)

    response = client.get("/api/vlm/models")
    data = response.get_json()

    assert response.status_code == 503
    assert "error" in data


def test_trigger_vlm_run_success(client, monkeypatch):
    payload = {"runId": 42, "modelId": "qwen/qwen2.5-vl-7b", "limit": 2}

    def fake_run(run_id, model_id, limit, **kwargs):
        fake_run.called_with = {"run_id": run_id, "model_id": model_id, "limit": limit, **kwargs}
        return {"runId": run_id, "processed": 2, "modelId": model_id}

    monkeypatch.setattr("app.api.vlm.run_vlm_for_run", fake_run)

    response = client.post("/api/vlm/run", json=payload)
    data = response.get_json()

    assert response.status_code == 200
    assert data["processed"] == 2
    assert fake_run.called_with["base_url"].startswith("http://")
    assert fake_run.called_with["model_id"] == payload["modelId"]


@pytest.mark.parametrize(
    "request_body,expected_error",
    [
        ({"modelId": "abc"}, "runId must be an integer"),
        ({"runId": 1}, "modelId is required"),
        ({"runId": 1, "modelId": "abc", "limit": 0}, "limit must be >= 1"),
    ],
)
def test_trigger_vlm_run_validation_errors(client, request_body, expected_error):
    response = client.post("/api/vlm/run", json=request_body)
    data = response.get_json()
    assert response.status_code == 400
    assert expected_error in data.get("error", "")


def test_trigger_vlm_run_failure_bubbles_error(client, monkeypatch):
    def fake_run(run_id, model_id, limit, **kwargs):
        raise VLMServiceError("boom")

    monkeypatch.setattr("app.api.vlm.run_vlm_for_run", fake_run)

    response = client.post("/api/vlm/run", json={"runId": 1, "modelId": "m", "limit": 1})
    data = response.get_json()
    assert response.status_code == 400
    assert "boom" in data.get("error", "")


def test_run_vlm_persists_overlay_metadata(client, monkeypatch, tmp_path):
    app = client.application
    app.config["LMSTUDIO_BASE_URL"] = "http://localhost:1234/v1"
    app.config["REPORTS_ROOT"] = str(tmp_path / "reports")

    frame_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAE0lEQVR42mP8z/C/HwAGgwJ/lkHhoAAAAABJRU5ErkJggg=="
    )

    with app.app_context():
        project = Project(name="Demo", description="")
        db.session.add(project)
        db.session.flush()

        video = Video(project_id=project.id, original_path="demo.mp4")
        db.session.add(video)
        db.session.flush()

        frame_path = tmp_path / "frame_000000.png"
        frame_path.write_bytes(frame_png)

        run = InferenceRun(
            project_id=project.id,
            video_id=video.id,
            model_ids=["model-A"],
            results={
                "frames": [
                    {
                        "index": 0,
                        "timestamp_seconds": 0.0,
                        "image_path": str(frame_path),
                    }
                ]
            },
            status="completed",
        )
        db.session.add(run)
        db.session.commit()

        def fake_run_frame(client_obj, model_id, image_path):
            return (
                [
                    {
                        "label": "Test Logo",
                        "confidence": 0.9,
                        "bbox": {
                            "left": 0.1,
                            "top": 0.1,
                            "right": 0.5,
                            "bottom": 0.5,
                        },
                    }
                ],
                640,
                480,
            )

        def fake_draw(image_path, detections, output_path, thickness=2, return_size=False):  # noqa: ARG001
            out_path = Path(output_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(b"overlay-bytes")
            return out_path

        monkeypatch.setattr("app.services.vlm_service._run_vlm_on_frame", fake_run_frame)
        monkeypatch.setattr("app.services.vlm_service.draw_frame_overlay", fake_draw)

        result = run_vlm_for_run(
            run.id,
            "qwen/qwen2.5-vl-7b",
            1,
            base_url=app.config["LMSTUDIO_BASE_URL"],
            api_key="token",
        )

        db.session.refresh(run)

        assert result["processed"] == 1
        assert result["modelId"] == "qwen/qwen2.5-vl-7b"
        assert Path(result["frames"][0]["overlayPath"]).is_file()

        overlays_meta = run.results.get("vlm_overlays") or {}
        assert overlays_meta.get("model_id") == "qwen/qwen2.5-vl-7b"
        assert "0" in overlays_meta.get("frames", {})

        vlm_detections = Detection.query.filter_by(
            inference_run_id=run.id,
            model_id="qwen/qwen2.5-vl-7b",
        ).all()
        assert len(vlm_detections) == 1

        response = client.get(
            f"/api/projects/{project.id}/videos/{video.id}/runs/{run.id}/detections"
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload["vlm_overlays"]["model_id"] == "qwen/qwen2.5-vl-7b"
        assert payload["frames"][0]["vlm_overlay_url"].startswith("/api/")

        overlay_resp = client.get(payload["frames"][0]["vlm_overlay_url"])
        assert overlay_resp.status_code == 200
        assert overlay_resp.data == b"overlay-bytes"