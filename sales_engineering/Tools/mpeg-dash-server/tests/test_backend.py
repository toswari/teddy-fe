import os
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def media_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("media")
    # Create a small dummy MP4 file (content is arbitrary; backend only checks extension)
    sample = root / "sample.mp4"
    sample.write_bytes(b"0123456789abcdef")
    return root


@pytest.fixture()
def app(media_root, monkeypatch):
    # Ensure MEDIA_ROOT is set before importing backend for this test process
    monkeypatch.setenv("MEDIA_ROOT", str(media_root))
    from importlib import reload

    # Ensure project root is on sys.path so `backend` is importable
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import backend.main as backend_main

    reload(backend_main)
    return backend_main.app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_video_full_file_ok(client, media_root):
    file_path = media_root / "sample.mp4"
    resp = client.get("/video", params={"path": str(file_path)})
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "video/mp4"
    body = resp.content
    assert body == b"0123456789abcdef"


def test_video_range_partial_content(client, media_root):
    file_path = media_root / "sample.mp4"
    resp = client.get("/video", params={"path": str(file_path)}, headers={"Range": "bytes=0-3"})
    assert resp.status_code == 206
    assert resp.headers.get("accept-ranges") == "bytes"
    assert resp.headers.get("content-range") == f"bytes 0-3/{len(b'0123456789abcdef')}"
    assert resp.content == b"0123"


def test_video_invalid_path_outside_media_root(client, media_root):
    # A path outside MEDIA_ROOT should be forbidden
    outside = Path("/tmp/other.mp4")
    resp = client.get("/video", params={"path": str(outside)})
    assert resp.status_code in {403, 404}


def test_video_path_traversal_blocked(client):
    resp = client.get("/video", params={"path": "../secret.mp4"})
    assert resp.status_code == 403


def test_video_invalid_range(client, media_root):
    file_path = media_root / "sample.mp4"
    # Start beyond end of file should yield 416
    resp = client.get("/video", params={"path": str(file_path)}, headers={"Range": "bytes=999-1000"})
    assert resp.status_code == 416


def test_health_returns_ok(client, media_root):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "media_root" in data


def test_package_dash_success(client, media_root, monkeypatch):
    file_path = media_root / "sample.mp4"
    from backend import main as backend_main

    def fake_package(source, output_dir, options=None):
        assert source == file_path
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / "manifest.mpd"
        manifest.write_text("<mpd />")
        return manifest

    monkeypatch.setattr(backend_main, "_package_to_dash", fake_package)
    monkeypatch.setattr(backend_main, "_ensure_ffmpeg_available", lambda: None)
    resp = client.post(
        "/api/dash/package",
        json={"path": str(file_path), "stream_id": "sample-stream"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["manifest"].endswith("manifest.mpd")
    assert data["output_dir"].startswith("sample-stream")


def test_package_dash_dynamic_options_pass_through(client, media_root, monkeypatch):
    file_path = media_root / "sample.mp4"
    from backend import main as backend_main

    captured = {}

    def fake_package(source, output_dir, options=None):
        captured["options"] = options
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / "manifest.mpd"
        manifest.write_text("<mpd />")
        return manifest

    monkeypatch.setattr(backend_main, "_package_to_dash", fake_package)
    monkeypatch.setattr(backend_main, "_ensure_ffmpeg_available", lambda: None)
    payload = {
        "path": str(file_path),
        "stream_id": "sample-stream",
        "options": {
            "mode": "dynamic",
            "reencode": True,
            "video_bitrate_kbps": 5500,
            "segment_padding": 0,
            "segment_template": "people_1920_1080_30fps_chunk_$RepresentationID$_$Number$.m4s",
            "init_segment_template": "people_1920_1080_30fps_init_$RepresentationID$.m4s",
            "segment_duration_seconds": 4,
            "window_size": 6,
            "extra_window_size": 6,
        },
    }
    resp = client.post("/api/dash/package", json=payload)
    assert resp.status_code == 200
    assert "options" in captured
    opts = captured["options"]
    assert opts is not None
    assert opts.mode == "dynamic"
    assert opts.reencode is True
    assert opts.segment_padding == 0
    assert opts.segment_template.startswith("people_1920_1080_30fps_chunk_")


def test_package_dash_invalid_file_rejected(client, media_root):
    bad_file = media_root / "not_video.txt"
    bad_file.write_text("nope")
    resp = client.post("/api/dash/package", json={"path": str(bad_file)})
    assert resp.status_code == 400


def test_package_dash_ffmpeg_failure_returns_stderr(client, media_root, monkeypatch):
    file_path = media_root / "sample.mp4"
    from backend import main as backend_main

    def fake_package(*_args, **_kwargs):
        raise HTTPException(status_code=500, detail={"error": "ffmpeg packaging failed", "stderr": "boom"})

    monkeypatch.setattr(backend_main, "_package_to_dash", fake_package)
    monkeypatch.setattr(backend_main, "_ensure_ffmpeg_available", lambda: None)
    resp = client.post("/api/dash/package", json={"path": str(file_path)})
    assert resp.status_code == 500
    data = resp.json()
    assert isinstance(data.get("detail"), dict)
    assert data["detail"].get("stderr") == "boom"


def test_media_listing_returns_mp4_and_mpd(client, media_root):
    dash_dir = media_root / "dash" / "stream1"
    dash_dir.mkdir(parents=True, exist_ok=True)
    manifest = dash_dir / "manifest.mpd"
    manifest.write_text("<mpd />")

    resp = client.get("/api/media")
    assert resp.status_code == 200
    data = resp.json()
    mp4_entries = data.get("mp4")
    mpd_entries = data.get("mpd")
    assert any(entry["path"].endswith("sample.mp4") for entry in mp4_entries)
    assert any(entry["path"].endswith("manifest.mpd") for entry in mpd_entries)
    # MPD entries should include a URL that clients can use directly
    mpd_with_url = [entry for entry in mpd_entries if entry["path"].endswith("manifest.mpd")]
    assert all("url" in entry for entry in mpd_with_url)
    assert all(entry["url"].startswith("http://testserver/dash/") for entry in mpd_with_url)

    def test_hls_streams_empty(client):
        meta = Path(os.getenv("MEDIA_ROOT", "media")) / ".hls_streams.json"
        if meta.exists():
            meta.unlink()
        resp = client.get("/api/hls/streams")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_hls_register_live_process_stub(client, monkeypatch):
        meta = Path(os.getenv("MEDIA_ROOT", "media")) / ".hls_streams.json"
        if meta.exists():
            meta.unlink()
        from backend import main as backend_main

        monkeypatch.setattr(backend_main, "_ensure_ffmpeg_available", lambda: None)
        monkeypatch.setattr(backend_main, "_build_hls_dash_command", lambda *args, **kwargs: ["echo", "ffmpeg"])

        class FakeProc:
            def __init__(self, *_args, **_kwargs):
                self.pid = 1234

        monkeypatch.setattr(backend_main.subprocess, "Popen", FakeProc)

        payload = {
            "name": "live-hls",
            "hls_url": "https://example.com/live/index.m3u8",
            "mode": "live",
        }
        resp = client.post("/api/hls/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["origin"] == "url"
        assert data["mpd_path"].startswith("/dash/")
        assert data["status"] in {"running", "starting", "completed"}

    def test_hls_upload_creates_manifest(client, media_root, monkeypatch, tmp_path):
        meta = Path(os.getenv("MEDIA_ROOT", "media")) / ".hls_streams.json"
        if meta.exists():
            meta.unlink()
        from backend import main as backend_main

        def fake_run(cmd, check, stdout, stderr):
            manifest_path = Path(cmd[-1])
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("<mpd />")
            class Result:
                pass
            return Result()

        monkeypatch.setattr(backend_main, "_ensure_ffmpeg_available", lambda: None)
        monkeypatch.setattr(backend_main.subprocess, "run", fake_run)

        archive = tmp_path / "sample.zip"
        playlist = "stream/index.m3u8"
        segment = "stream/seg1.ts"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr(playlist, "#EXTM3U\n#EXTINF:4,\nseg1.ts\n")
            zf.writestr(segment, "data")

        with archive.open("rb") as fh:
            files = {"file": ("sample.zip", fh.read(), "application/zip")}
        data = {"name": "upload-hls"}
        resp = client.post("/api/hls/upload", files=files, data=data)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["origin"] == "upload"
        assert payload["status"] == "completed"
        assert payload["mpd_path"].endswith("manifest.mpd")
