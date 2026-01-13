"""Tests to ensure SocketIO inference events are emitted during runs."""
from __future__ import annotations

from app.extensions import db, socketio
from app.models import Detection, Project, Video
from app.services import inference_service


def _seed_project_video(tmp_path):
    project = Project(name="SocketIO Test", description="", settings={})
    video = Video(
        project=project,
        original_path=str(tmp_path / "video.mp4"),
        storage_path=str(tmp_path / "video.mp4"),
        status="processed",
        duration_seconds=10,
    )
    db.session.add_all([project, video])
    db.session.commit()
    return project, video


def test_inference_emits_socketio_events(app, tmp_path, monkeypatch):
    with app.app_context():
        project, video = _seed_project_video(tmp_path)

        emitted = []

        def fake_emit(event, payload):
            emitted.append((event, payload))

        monkeypatch.setattr(socketio, "emit", fake_emit)

        # Mock sampling to avoid needing a real video container
        frames = [
            inference_service.FrameSample(index=0, timestamp_seconds=0.0, payload=b"frame0"),
            inference_service.FrameSample(index=1, timestamp_seconds=1.0, payload=b"frame1"),
        ]
        monkeypatch.setattr(inference_service, "sample_frames", lambda v, fps, source_override=None: frames)
        # Prevent external Clarifai calls by stubbing the client run_models
        def fake_run_models(self, frames_arg, model_ids_arg, params_arg):
            # Return a single fake detection for the first frame
            return [
                {
                    "frame_index": frames_arg[0].index,
                    "timestamp_seconds": frames_arg[0].timestamp_seconds,
                    "model_id": (model_ids_arg[0] if model_ids_arg else "stub-model"),
                    "label": "stub",
                    "confidence": 0.9,
                    "bbox": {"top": 0.1, "left": 0.1, "bottom": 0.5, "right": 0.5},
                }
            ]

        monkeypatch.setattr(inference_service.ClarifaiClient, "run_models", fake_run_models, raising=False)

        # Run inference with default (stub) client
        request = inference_service.InferenceRequest()
        run = inference_service.run_inference(video, request)

        # Ensure top-level running/completed events emitted
        events = [e for e, _ in emitted]
        assert any(e == "inference:update" for e in events)
        assert run.status in ("completed", "failed")


def test_local_vlm_models_bypass_clarifai(app, tmp_path, monkeypatch):
    with app.app_context():
        app.config["PROJECT_MEDIA_ROOT"] = str(tmp_path / "media")
        _, video = _seed_project_video(tmp_path)

        frames = [
            inference_service.FrameSample(index=0, timestamp_seconds=0.0, payload=b"frame0"),
            inference_service.FrameSample(index=1, timestamp_seconds=1.0, payload=b"frame1"),
        ]
        monkeypatch.setattr(
            inference_service,
            "sample_frames",
            lambda v, fps, source_override=None: frames,
        )

        clarifai_calls: list[list[str]] = []

        def fake_run_models(self, frames_arg, model_ids_arg, params_arg):
            clarifai_calls.append(model_ids_arg)
            return []

        monkeypatch.setattr(
            inference_service.ClarifaiClient,
            "run_models",
            fake_run_models,
            raising=False,
        )

        vlm_calls: list[str] = []

        def fake_run_vlm_for_run(run_id, model_id, limit, *, base_url, api_key, project_root=None):
            vlm_calls.append(model_id)
            inference_run = db.session.get(inference_service.InferenceRun, run_id)
            frame_meta = (inference_run.results or {}).get("frames") or []
            first = frame_meta[0] if frame_meta else {"index": 0, "timestamp_seconds": 0.0, "image_path": None}
            detection = Detection(
                inference_run_id=run_id,
                frame_index=first.get("index"),
                timestamp_seconds=first.get("timestamp_seconds"),
                model_id=model_id,
                label="local-vlm",
                confidence=0.75,
                bbox={"top": 0.1, "left": 0.1, "bottom": 0.3, "right": 0.3},
                frame_image_path=first.get("image_path"),
            )
            db.session.add(detection)
            existing = dict(inference_run.results or {})
            overlay_path = f"/fake/{model_id}/{first.get('index', 0)}.png"
            existing["vlm_overlays"] = {
                "model_id": model_id,
                "frames": {
                    str(first.get("index", 0)): {"overlayPath": overlay_path},
                },
            }
            inference_run.results = existing
            db.session.commit()
            return {
                "processed": 1,
                "modelId": model_id,
                "frames": [
                    {
                        "frameIndex": first.get("index", 0),
                        "overlayPath": overlay_path,
                    }
                ],
            }

        monkeypatch.setattr(
            inference_service,
            "run_vlm_for_run",
            fake_run_vlm_for_run,
        )

        request = inference_service.InferenceRequest(model_ids=["qwen/qwen2.5-vl-7b"])
        run = inference_service.run_inference(video, request)

        assert clarifai_calls == []
        assert vlm_calls == ["qwen/qwen2.5-vl-7b"]
        assert run.status == "completed"

        overlays_meta = run.results.get("vlm_overlays") or {}
        assert overlays_meta.get("model_id") == "qwen/qwen2.5-vl-7b"

        vlm_detections = Detection.query.filter_by(
            inference_run_id=run.id,
            model_id="qwen/qwen2.5-vl-7b",
        ).all()
        assert len(vlm_detections) == 1