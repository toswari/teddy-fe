"""Clarifai inference helpers (reference implementation stubs)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import cv2
import av

from app.extensions import db
from app.models import InferenceRun, Video
logger = logging.getLogger(__name__)



def sample_frames(video_path: str, fps: float = 1.0) -> list[bytes]:
    """Sample frames from video at given FPS, return as JPEG bytes."""
    frames = []
    container = av.open(video_path)
    stream = container.streams.video[0]
    duration = float(stream.duration * stream.time_base)
    
    for timestamp in range(0, int(duration), int(1 / fps)):
        container.seek(timestamp, stream=stream)
        for frame in container.decode(stream):
            if frame.time >= timestamp:
                img = frame.to_image()
                # Convert to JPEG bytes
                import io
                buf = io.BytesIO()
                img.save(buf, format='JPEG')
                frames.append(buf.getvalue())
                break
    return frames


class ClarifaiClientStub:
    """Real Clarifai client using SDK."""

    def __init__(self, pat: str | None = None) -> None:
        from clarifai.client.model import Model
        import os
        self.pat = pat or os.getenv("CLARIFAI_PAT")
        self.user_id = os.getenv("CLARIFAI_USER_ID")
        self.app_id = os.getenv("CLARIFAI_APP_ID")

    def run_models(self, frames: list[bytes], model_ids: list[str]) -> list[dict]:
        detections = []
        for model_id in model_ids:
            model = Model(model_id, pat=self.pat, user_id=self.user_id, app_id=self.app_id)
            for i, frame_bytes in enumerate(frames):
                try:
                    response = model.predict_by_bytes(frame_bytes, input_type="image")
                    # Parse response
                    concepts = response.outputs[0].data.concepts
                    for concept in concepts:
                        detections.append({
                            "frame_index": i,
                            "model_id": model_id,
                            "label": concept.name,
                            "confidence": concept.value,
                        })
                except Exception as e:
                    logger.error("Clarifai prediction failed for model %s: %s", model_id, e)
        return detections


def run_inference(video: Video, model_ids: list[str]) -> InferenceRun:
    inference_run = InferenceRun(project_id=video.project_id, video_id=video.id, model_ids=model_ids)
    db.session.add(inference_run)
    db.session.commit()
    logger.info(
        "Inference run created (run_id=%s, video_id=%s, models=%s)",
        inference_run.id,
        video.id,
        model_ids,
    )

    # Sample frames
    frames = sample_frames(video.original_path, fps=1.0)
    logger.debug("Sampled %s frames from video %s", len(frames), video.id)

    # Run inference
    client = ClarifaiClientStub()
    detections = client.run_models(frames, model_ids)
    inference_run.results = {"detections": detections}
    inference_run.status = "completed"
    db.session.commit()
    logger.debug("Inference completed (run_id=%s, detections=%s)", inference_run.id, len(detections))
    return inference_run
