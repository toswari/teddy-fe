"""Video ingestion and pre-processing helpers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.extensions import db
from app.models import Video
logger = logging.getLogger(__name__)



class VideoProcessingError(RuntimeError):
    """Raised when FFmpeg/PyAV work fails."""


def register_video(project_id: int, source_path: str) -> Video:
    video = Video(project_id=project_id, original_path=source_path)
    db.session.add(video)
    db.session.commit()
    logger.info("Video registered (id=%s, project_id=%s)", video.id, project_id)
    return video


def probe_video_metadata(video: Video) -> dict[str, Any]:
    # Reference stub: integrate ffmpeg.probe or av.open in real implementation.
    fake_metadata = {"duration_seconds": 120, "resolution": "1920x1080"}
    video.duration_seconds = fake_metadata["duration_seconds"]
    video.resolution = fake_metadata["resolution"]
    db.session.commit()
    logger.debug("Video metadata probed (id=%s, metadata=%s)", video.id, fake_metadata)
    return fake_metadata


def generate_clips(video: Video, clip_length: int = 20) -> list[Path]:
    # Stub implementation that shows expected return signature.
    clips_root = Path("media") / f"project_{video.project_id}" / f"video_{video.id}"
    clips_root.mkdir(parents=True, exist_ok=True)
    clip_path = clips_root / "clip_001.mp4"
    clip_path.touch()
    video.status = "processed"
    db.session.commit()
    logger.info("Video processed into %s clip(s) (id=%s)", len(clips := [clip_path]), video.id)
    return clips
