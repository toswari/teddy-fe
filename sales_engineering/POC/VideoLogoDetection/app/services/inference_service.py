"""Clarifai inference helpers (reference implementation stubs)."""
from __future__ import annotations

import logging
from typing import Iterable

from app.extensions import db
from app.models import InferenceRun, Video
logger = logging.getLogger(__name__)



class ClarifaiClientStub:
    """Drop-in stand-in for the real Clarifai SDK usage.

    Replace with something like:

    ```python
    from clarifai.client.model import Model
    model = Model(model_id)
    response = model.predict_by_bytes(frame_bytes)
    ```

    Keeping this stub documented helps downstream agents know exactly
    where to plug the official SDK calls.
    """

    def __init__(self, pat: str | None = None) -> None:
        self.pat = pat

    def run_models(self, frames: Iterable[str], model_ids: list[str]) -> list[dict]:
        detections = []
        for frame in frames:
            for model in model_ids:
                detections.append(
                    {
                        "frame": frame,
                        "model_id": model,
                        "label": "sample-logo",
                        "confidence": 0.87,
                    }
                )
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

    client = ClarifaiClientStub()
    frames = ["frame_001.jpg", "frame_020.jpg"]
    detections = client.run_models(frames, model_ids)
    inference_run.results = {"detections": detections}
    inference_run.status = "completed"
    db.session.commit()
    logger.debug("Inference completed (run_id=%s, detections=%s)", inference_run.id, len(detections))
    return inference_run
