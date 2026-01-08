"""Regression tests for inference run inspection endpoints."""
from __future__ import annotations

from app.extensions import db
from app.models import Detection, InferenceRun, Project, Video


def _seed_project_with_run():
    project = Project(name="Test", description="", settings={})
    video = Video(
        project=project,
        original_path="/tmp/original.mp4",
        storage_path="/tmp/original.mp4",
        status="processed",
    )
    inference_run = InferenceRun(
        project=project,
        video=video,
        model_ids=["model/a", "model/b"],
        params={"fps": 1.0},
        status="completed",
        results={
            "frames": [
                {
                    "index": 0,
                    "timestamp_seconds": 0.0,
                }
            ]
        },
    )
    detection = Detection(
        inference_run=inference_run,
        frame_index=0,
        timestamp_seconds=0.0,
        model_id="model/a",
        label="example",
        confidence=0.9,
        bbox={
            "top": 0.1,
            "left": 0.1,
            "bottom": 0.5,
            "right": 0.5,
        },
    )
    db.session.add_all([project, video, inference_run, detection])
    db.session.commit()
    return project, video, inference_run


def test_run_detections_preserve_model_order(client, app):
    with app.app_context():
        project, video, inference_run = _seed_project_with_run()
        project_id = project.id
        video_id = video.id
        run_id = inference_run.id

    response = client.get(
        f"/api/projects/{project_id}/videos/{video_id}/runs/{run_id}/detections"
    )
    assert response.status_code == 200
    payload = response.get_json()

    # Model order should match the saved request order
    assert payload["models"] == ["model/a", "model/b"], payload["models"]

    # Grouped detections should be present for all models, even if some are empty
    assert payload["detections_by_model"]["model/a"], "Expected detections for model/a"
    assert payload["detections_by_model"]["model/b"] == []

    # Frame metadata should include generated image URLs for playback
    assert payload["frames"], "Expected at least one frame entry"
    frame_entry = payload["frames"][0]
    assert frame_entry["image_url"].endswith("/frames/0"), frame_entry