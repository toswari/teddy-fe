"""Tests for video report endpoint."""
from __future__ import annotations

from pathlib import Path


def test_generate_video_report_endpoint(client, monkeypatch, tmp_path):
    # Create project and video
    client.post("/api/projects", json={"name": "P", "description": "d"})
    
    # Create dummy video file
    dummy_video = tmp_path / "dummy.mp4"
    dummy_video.write_bytes(b"")
    
    # Mock video registration
    from app.services import video_service
    orig_register = video_service.register_video
    
    def fake_register(project_id, source_path):
        return orig_register(project_id, str(dummy_video))
    
    monkeypatch.setattr(video_service, "register_video", fake_register)
    monkeypatch.setattr(video_service, "probe_video_metadata", lambda v: setattr(v, "duration_seconds", 60) or {})
    monkeypatch.setattr(video_service, "generate_clips", lambda v, **kw: [Path("fake.mp4")])
    
    rv = client.post("/api/projects/1/videos", json={"source_path": str(dummy_video)})
    assert rv.status_code == 201
    vid = rv.get_json()["id"]
    
    # Call report endpoint
    rv2 = client.post(f"/api/projects/1/videos/{vid}/report")
    assert rv2.status_code == 201
    data = rv2.get_json()
    assert "report_path" in data