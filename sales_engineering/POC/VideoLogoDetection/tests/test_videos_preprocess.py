"""Tests for video preprocessing endpoint."""
from __future__ import annotations

from pathlib import Path


def test_preprocess_multiple_clips_endpoint(client, monkeypatch, tmp_path):
    # Create a dummy project and register a video record by copying an empty file
    # Create a minimal video file placeholder
    media_root = tmp_path / "media"
    media_root.mkdir()
    dummy_video = tmp_path / "sample.mp4"
    dummy_video.write_bytes(b"")

    # Register project
    client.post("/api/projects", json={"name": "P", "description": "d"})

    # Monkeypatch register_video to use our dummy file path
    from app.services import video_service

    orig_register = video_service.register_video

    def fake_register_video(project_id, source_path):
        # call the original register_video but force the source_path to our dummy file
        return orig_register(project_id, str(dummy_video))

    monkeypatch.setattr(video_service, "register_video", fake_register_video)

    # Monkeypatch probe and generate_multiple_clips to avoid ffmpeg
    def fake_probe(video):
        video.duration_seconds = 60
        video.video_metadata = {**(video.video_metadata or {}), "duration_seconds": 60}
        return video.video_metadata

    def fake_generate_multiple_clips(video, clips):
        # Return fake paths
        root = Path(video.storage_path).parent / "clips"
        root.mkdir(parents=True, exist_ok=True)
        results = []
        for i, seg in enumerate(clips, start=1):
            p = root / f"clip{i}.mp4"
            p.write_bytes(b"")
            results.append(p)
        return results

    monkeypatch.setattr(video_service, "probe_video_metadata", fake_probe)
    monkeypatch.setattr(video_service, "generate_multiple_clips", fake_generate_multiple_clips)
    # Also monkeypatch generate_clips used during registration to avoid ffmpeg
    def fake_generate_clips(video, clip_length=20, start_seconds=None, duration_seconds=None):
        root = Path(video.storage_path).parent / "clips"
        root.mkdir(parents=True, exist_ok=True)
        p = root / "sample-clip1.mp4"
        p.write_bytes(b"")
        # Update metadata similarly
        video.status = "processed"
        video.video_metadata = {**(video.video_metadata or {}), "clips": [{"path": str(p), "start": 0, "end": 5, "segment": 1, "duration": 5}], "last_preprocess_window": {"clip_count": 1}}
        return [p]

    monkeypatch.setattr(video_service, "generate_clips", fake_generate_clips)

    # Register video via API (path-based)
    rv = client.post(
        "/api/projects/1/videos",
        json={"source_path": str(dummy_video)},
    )
    assert rv.status_code == 201
    vid = rv.get_json()["id"]

    # Call preprocess with multiple segments
    payload = {"clips": [{"start": 0.0, "end": 5.0}, {"start": 10.0, "end": 15.0}]}
    rv2 = client.post(f"/api/projects/1/videos/{vid}/preprocess", json=payload)
    assert rv2.status_code == 200
    data = rv2.get_json()
    assert data["video_id"] == vid
    assert data["status"] == "processed"
    assert len(data["clips"]) == 2
