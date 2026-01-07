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
    import av
    try:
        container = av.open(video.original_path)
        stream = container.streams.video[0]
        duration_seconds = float(stream.duration * stream.time_base) if stream.duration else 0
        resolution = f"{stream.width}x{stream.height}"
        metadata = {
            "duration_seconds": duration_seconds,
            "resolution": resolution,
            "frame_rate": float(stream.average_rate) if stream.average_rate else 0,
        }
        video.duration_seconds = int(duration_seconds)
        video.resolution = resolution
        db.session.commit()
        logger.debug("Video metadata probed (id=%s, metadata=%s)", video.id, metadata)
        return metadata
    except Exception as e:
        logger.error("Failed to probe video metadata for %s: %s", video.original_path, e)
        raise VideoProcessingError(f"Metadata probing failed: {e}")


def generate_clips(video: Video, clip_length: int = 20) -> list[Path]:
    import ffmpeg
    clips = []
    duration = video.duration_seconds
    if not duration:
        raise VideoProcessingError("Video duration unknown, cannot generate clips")
    
    clips_root = Path("media") / f"project_{video.project_id}" / f"video_{video.id}" / "clips"
    clips_root.mkdir(parents=True, exist_ok=True)
    
    for start_time in range(0, duration, clip_length):
        end_time = min(start_time + clip_length, duration)
        clip_path = clips_root / f"clip_{start_time:04d}_{end_time:04d}.mp4"
        try:
            ffmpeg.input(video.original_path, ss=start_time, t=clip_length).output(
                str(clip_path), c="copy", avoid_negative_ts="make_zero"
            ).run(quiet=True)
            clips.append(clip_path)
        except ffmpeg.Error as e:
            logger.error("Failed to generate clip %s: %s", clip_path, e)
            raise VideoProcessingError(f"Clip generation failed: {e}")
    
    video.status = "processed"
    db.session.commit()
    logger.info("Video processed into %s clip(s) (id=%s)", len(clips), video.id)
    return clips
