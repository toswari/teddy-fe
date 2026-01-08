"""Video ingestion and pre-processing helpers."""
from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path
from typing import Any

from flask import current_app
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Video
logger = logging.getLogger(__name__)



class VideoProcessingError(RuntimeError):
    """Raised when FFmpeg/PyAV work fails."""


DEFAULT_MAX_CLIPS = 450


def register_uploaded_video(project_id: int, file: FileStorage) -> Video:
    """Register a video from a file upload."""
    if not file.filename:
        raise VideoProcessingError("No filename provided")
    
    # Secure the filename
    import re
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
    
    metadata = {
        "original_filename": file.filename,
    }
    video = Video(project_id=project_id, original_path=filename, video_metadata=metadata)
    db.session.add(video)
    
    try:
        db.session.flush()
        media_root = Path(current_app.config.get("PROJECT_MEDIA_ROOT", "media"))
        storage_dir = media_root / f"project_{project_id}" / f"video_{video.id}"
        storage_dir.mkdir(parents=True, exist_ok=True)
        dest_file = storage_dir / f"video_{video.id}_{filename}"
        
        # Save uploaded file
        file.save(str(dest_file))
        
        video.storage_path = str(dest_file)
        video.video_metadata = {**(video.video_metadata or {}), "storage_path": str(dest_file)}
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("Failed to save uploaded video for project %s: %s", project_id, exc)
        raise VideoProcessingError("Unable to persist uploaded video") from exc
    
    logger.info("Video uploaded and registered (id=%s, project_id=%s)", video.id, project_id)
    return video


def register_video(project_id: int, source_path: str) -> Video:
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise VideoProcessingError(f"Source video file not found: {source}")

    metadata = {
        "original_filename": source.name,
    }
    video = Video(project_id=project_id, original_path=str(source), video_metadata=metadata)
    db.session.add(video)
    try:
        db.session.flush()
        media_root = Path(current_app.config.get("PROJECT_MEDIA_ROOT", "media"))
        storage_dir = media_root / f"project_{project_id}" / f"video_{video.id}"
        storage_dir.mkdir(parents=True, exist_ok=True)
        dest_file = storage_dir / f"video_{video.id}_{source.name}"
        shutil.copy2(source, dest_file)
        video.storage_path = str(dest_file)
        video.video_metadata = {**(video.video_metadata or {}), "storage_path": str(dest_file)}
        db.session.commit()
    except Exception as exc:  # pragma: no cover - best-effort storage
        db.session.rollback()
        logger.error("Failed to register video %s for project %s: %s", source, project_id, exc)
        raise VideoProcessingError("Unable to persist uploaded video") from exc

    logger.info("Video registered (id=%s, project_id=%s)", video.id, project_id)
    return video


def probe_video_metadata(video: Video) -> dict[str, Any]:
    import av

    source_path = Path(video.storage_path or video.original_path)
    if not source_path.is_file():
        raise VideoProcessingError(f"Cannot probe missing video file: {source_path}")

    try:
        container = av.open(str(source_path))
        stream = container.streams.video[0]
        duration = 0.0
        if stream.duration and stream.time_base:
            duration = float(stream.duration * stream.time_base)
        resolution = f"{stream.width}x{stream.height}"
        frame_rate = float(stream.average_rate) if stream.average_rate else 0.0
        metadata = {
            "duration_seconds": duration,
            "resolution": resolution,
            "frame_rate": frame_rate,
            "storage_path": str(source_path),
        }
        video.duration_seconds = int(duration)
        video.resolution = resolution
        video.video_metadata = {**(video.video_metadata or {}), **metadata}
        db.session.commit()
        logger.debug("Video metadata probed (id=%s, metadata=%s)", video.id, metadata)
        return metadata
    except Exception as exc:
        logger.error("Failed to probe video metadata for %s: %s", source_path, exc)
        raise VideoProcessingError(f"Metadata probing failed: {exc}") from exc


def generate_clips(
    video: Video,
    clip_length: int = 20,
    *,
    start_seconds: float | None = None,
    duration_seconds: float | None = None,
) -> list[Path]:
    """Split a video into fixed-length clips, honoring optional window bounds."""

    import ffmpeg

    if clip_length <= 0:
        raise VideoProcessingError("Clip length must be greater than zero")

    total_seconds = int(video.duration_seconds or 0)
    if total_seconds <= 0:
        raise VideoProcessingError("Video duration unknown, cannot generate clips")

    start_offset = int(max(0, math.floor(start_seconds or 0)))
    if start_offset >= total_seconds:
        raise VideoProcessingError("Start time exceeds video duration")

    remaining = total_seconds - start_offset
    if duration_seconds is not None:
        requested = max(1, int(math.ceil(duration_seconds)))
        window_duration = min(requested, remaining)
    else:
        window_duration = remaining

    if window_duration <= 0:
        raise VideoProcessingError("Requested window has no duration")

    end_offset = start_offset + window_duration

    clip_count = math.ceil(window_duration / clip_length)
    max_clips = int(current_app.config.get("MAX_VIDEO_CLIPS", DEFAULT_MAX_CLIPS))
    if clip_count > max_clips:
        raise VideoProcessingError(
            f"Requested window would create {clip_count} clips, exceeding limit of {max_clips}"
        )

    media_root = Path(current_app.config.get("PROJECT_MEDIA_ROOT", "media"))
    clips_root = media_root / f"project_{video.project_id}" / f"video_{video.id}" / "clips"
    clips_root.mkdir(parents=True, exist_ok=True)

    source_path = video.storage_path or video.original_path
    clips: list[Path] = []
    clip_records = []

    # Extract and sanitize original filename for clip naming
    original_filename = video.video_metadata.get("original_filename") or video.original_path or f"video_{video.id}"
    import re
    base_name = re.sub(r'\.[^.]+$', '', original_filename)  # Remove extension
    base_name = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name)  # Sanitize special characters

    for start_time in range(start_offset, end_offset, clip_length):
        clip_end = min(start_time + clip_length, end_offset)
        clip_duration = clip_end - start_time
        if clip_duration <= 0:
            continue
        clip_path = clips_root / f"{base_name}-clip{len(clips)+1}.mp4"
        try:
            ffmpeg.input(source_path, ss=start_time, t=clip_duration).output(
                str(clip_path), c="copy", avoid_negative_ts="make_zero"
            ).run(quiet=True)
        except ffmpeg.Error as exc:
            logger.error("Failed to generate clip %s: %s", clip_path, exc)
            raise VideoProcessingError(f"Clip generation failed: {exc}") from exc

        clips.append(clip_path)
        clip_records.append(
            {
                "path": str(clip_path),
                "start": start_time,
                "end": clip_end,
                "segment": len(clips),
                "duration": clip_duration,
            }
        )

    window_meta = {
        "start": start_offset,
        "duration": window_duration,
        "end": end_offset,
        "clip_length": clip_length,
        "clip_count": len(clips),
        "total_duration": window_duration,
    }

    video.status = "processed"
    video.video_metadata = {
        **(video.video_metadata or {}),
        "clips": clip_records,
        "last_preprocess_window": window_meta,
    }
    db.session.commit()
    return clips


def generate_multiple_clips(video: Video, clip_segments: list[dict[str, float]]) -> list[Path]:
    """Generate multiple clips from specified time segments."""

    import ffmpeg
    import re

    if len(clip_segments) > 5:
        raise VideoProcessingError("Maximum 5 clip segments allowed")

    total_seconds = int(video.duration_seconds or 0)
    if total_seconds <= 0:
        raise VideoProcessingError("Video duration unknown, cannot generate clips")

    # Extract and sanitize original filename for clip naming
    original_filename = video.video_metadata.get("original_filename") or video.original_path or f"video_{video.id}"
    # Remove file extension and sanitize for filesystem
    base_name = re.sub(r'\.[^.]+$', '', original_filename)  # Remove extension
    base_name = re.sub(r'[^a-zA-Z0-9_-]', '_', base_name)  # Sanitize special characters

    media_root = Path(current_app.config.get("PROJECT_MEDIA_ROOT", "media"))
    clips_root = media_root / f"project_{video.project_id}" / f"video_{video.id}" / "clips"
    clips_root.mkdir(parents=True, exist_ok=True)

    source_path = video.storage_path or video.original_path
    clips: list[Path] = []
    clip_records = []
    total_duration = 0.0

    for i, segment in enumerate(clip_segments):
        start_time = segment.get("start", 0)
        end_time = segment.get("end", 0)
        
        if start_time >= end_time:
            raise VideoProcessingError(f"Invalid segment {i+1}: start time must be before end time")
        if start_time < 0 or end_time > total_seconds:
            raise VideoProcessingError(f"Segment {i+1} times are outside video duration")
        
        clip_duration = end_time - start_time
        clip_path = clips_root / f"{base_name}-clip{i+1}.mp4"
        
        try:
            ffmpeg.input(source_path, ss=start_time, t=clip_duration).output(
                str(clip_path), c="copy", avoid_negative_ts="make_zero"
            ).run(quiet=True)
        except ffmpeg.Error as exc:
            logger.error("Failed to generate clip %s: %s", clip_path, exc)
            raise VideoProcessingError(f"Clip generation failed for segment {i+1}: {exc}") from exc

        clips.append(clip_path)
        total_duration += clip_duration
        clip_records.append(
            {
                "path": str(clip_path),
                "start": start_time,
                "end": end_time,
                "segment": i+1,
                "duration": clip_duration,
            }
        )

    window_meta = {
        "clip_count": len(clips),
        "segments": clip_records,
        "total_duration": total_duration,
    }

    video.status = "processed"
    video.video_metadata = {
        **(video.video_metadata or {}),
        "clips": clip_records,
        "last_preprocess_window": window_meta,
    }
    db.session.commit()
    logger.info(
        "Video processed into %s clip(s) from %s segment(s) (id=%s)",
        len(clips),
        len(clip_segments),
        video.id,
    )
    return clips
