"""Background tasks for the in-process queue."""
from __future__ import annotations

from app.extensions import db
from app.models import InferenceRun, Video
from app.services import inference_service, video_service
from app.services.inference_models import InferenceRequest


def preprocess_video_task(video_id: int, options: dict | None):
    video = db.session.get(Video, video_id)
    if not video:
        return
    try:
        payload = dict(options or {})
        clips_payload = payload.pop("clips", None)
        video_service.probe_video_metadata(video)
        if clips_payload:
            video_service.generate_multiple_clips(video, clips_payload)
        else:
            video_service.generate_clips(video, **payload)
        video.status = "processed"
        db.session.commit()
    except Exception:
        video.status = "failed"
        db.session.commit()
        raise


def run_inference_task(run_id: int):
    inference_run = db.session.get(InferenceRun, run_id)
    if not inference_run:
        return
    try:
        params = inference_run.params or {}
        request = InferenceRequest(
            model_ids=inference_run.model_ids,
            params=params,
            clip_id=params.get("clip_id"),
        )
        inference_service.run_inference(inference_run.video, request)
    except Exception as exc:
        inference_run.status = "failed"
        inference_run.results = {"error": str(exc)}
        db.session.commit()
        raise