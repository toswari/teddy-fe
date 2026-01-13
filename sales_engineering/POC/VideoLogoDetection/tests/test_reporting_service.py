"""Tests for reporting export helpers with VLM data."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from app.extensions import db
from app.models import Detection, InferenceRun, Project, Video


def test_build_run_export_normalizes_vlm_bbox(app, client, tmp_path):
    with app.app_context():
        app.config["PROJECT_MEDIA_ROOT"] = str(tmp_path)
        app.config["REPORTS_ROOT"] = str(tmp_path / "reports")

        project = Project(name="Export Test", description="", settings={})
        video = Video(
            project=project,
            original_path=str(tmp_path / "video.mp4"),
            storage_path=str(tmp_path / "video.mp4"),
            status="processed",
            duration_seconds=10,
        )
        db.session.add_all([project, video])
        db.session.commit()

        frame_path = tmp_path / "frame.jpg"
        frame_image = np.zeros((180, 200, 3), dtype=np.uint8)
        cv2.imwrite(str(frame_path), frame_image)

        run = InferenceRun(
            project_id=project.id,
            video_id=video.id,
            model_ids=["clarifai/model-A", "qwen/qwen2.5-vl-7b"],
            params={},
            status="completed",
            results={
                "frames": [
                    {
                        "index": 0,
                        "timestamp_seconds": 0.0,
                        "image_path": str(frame_path),
                    }
                ],
                "vlm_overlays": {"model_id": "qwen/qwen2.5-vl-7b", "frames": {}},
            },
        )
        db.session.add(run)
        db.session.commit()

        detection = Detection(
            inference_run_id=run.id,
            frame_index=0,
            timestamp_seconds=0.5,
            model_id="qwen/qwen2.5-vl-7b",
            label="Sample Logo",
            confidence=0.85,
            bbox={"left": 50, "top": 60, "right": 150, "bottom": 120},
            frame_image_path=str(frame_path),
        )
        db.session.add(detection)
        db.session.commit()

        run_id = run.id
        project_id = project.id
        video_id = video.id

    response = client.get(f"/api/projects/{project_id}/videos/{video_id}/runs/{run_id}/export")
    assert response.status_code == 200
    assert response.headers.get("Content-Type", "").startswith("application/zip")

    fallback = client.get(f"/api/reports/run/{run_id}/download")
    assert fallback.status_code == 200

    run_dir = Path(app.config["REPORTS_ROOT"]) / f"run_{run_id}"
    overlay_path = run_dir / "frames" / "frame_000000_overlay.png"
    assert overlay_path.is_file()

    overlay_img = cv2.imread(str(overlay_path))
    assert overlay_img is not None
    assert overlay_img[5, 5].sum() == 0
    assert overlay_img[55:65, 45:55].sum() > 0

    aggregate_path = run_dir / "json" / "detections_aggregate.json"
    data = json.loads(aggregate_path.read_text())
    frame_entry = data["frames"][0]
    bbox_norm = frame_entry["detections"][0]["bboxNormalized"]
    assert 0.24 < bbox_norm["left"] < 0.26
    assert 0.32 < bbox_norm["top"] < 0.35
    assert 0.74 < bbox_norm["right"] < 0.76
    assert 0.65 < bbox_norm["bottom"] < 0.67