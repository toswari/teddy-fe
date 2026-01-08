"""Tests to ensure SocketIO inference events are emitted during runs."""
from __future__ import annotations

from app.extensions import db, socketio
from app.models import Project, Video
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