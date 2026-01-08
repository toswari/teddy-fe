"""Clarifai inference helpers aligned with the MVP implementation plan."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import av
import cv2

from app.extensions import db, socketio
from app.models import Detection, InferenceRun, Video
from .inference_models import InferenceRequest, InferenceParams
from . import billing_service

logger = logging.getLogger(__name__)


class InferenceServiceError(RuntimeError):
    """Raised when Clarifai inference fails."""


@dataclass
class FrameSample:
    index: int
    timestamp_seconds: float
    payload: bytes


def _emit_status(event: str, payload: dict) -> None:
    """Emit Socket.IO status messages without breaking on failure."""
    try:
        socketio.emit(event, payload)
    except Exception:  # pragma: no cover - socket errors should not kill request
        logger.debug("SocketIO emit failed for event=%s", event, exc_info=True)


def sample_frames(video: Video, fps: float, *, source_override: str | None = None) -> List[FrameSample]:
    """Sample frames from a video or clip at the requested FPS, return JPEG payloads."""
    if fps <= 0:
        raise InferenceServiceError("Sampling FPS must be positive")

    source = Path(source_override or video.storage_path or video.original_path or "")
    if not source.is_file():
        raise InferenceServiceError(f"Video source not found for sampling: {source}")

    container = av.open(str(source))
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"

    samples: List[FrameSample] = []
    interval = 1.0 / fps
    next_capture = 0.0

    try:
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            timestamp = float(frame.time)
            if timestamp + 1e-6 < next_capture:
                continue
            image = frame.to_ndarray(format="bgr24")
            success, buffer = cv2.imencode(".jpg", image)
            if not success:
                logger.debug("Failed to encode frame at %.3fs", timestamp)
                continue
            samples.append(
                FrameSample(
                    index=len(samples),
                    timestamp_seconds=timestamp,
                    payload=buffer.tobytes(),
                )
            )
            next_capture += interval
    finally:
        container.close()

    logger.debug("Sampled %s frame(s) from video id=%s", len(samples), video.id)
    return samples


def _format_clock(seconds: float | int | None) -> str:
    if seconds is None:
        return "0:00"
    value = max(0.0, float(seconds))
    minutes, sec = divmod(int(value + 0.5), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _parse_clip_identifier(clip_id: str, video_id: int) -> int:
    candidate = clip_id or ""
    segment_part = candidate
    if "-" in candidate:
        prefix, suffix = candidate.split("-", 1)
        try:
            prefix_id = int(prefix)
            if prefix_id != video_id:
                logger.debug("Clip identifier video mismatch: expected %s, got %s", video_id, prefix_id)
        except ValueError:
            # Prefix is not numeric; treat entire string as segment
            suffix = candidate
        segment_part = suffix
    try:
        return int(segment_part)
    except (TypeError, ValueError) as exc:
        raise InferenceServiceError(f"Invalid clip identifier: {clip_id}") from exc


def _resolve_clip_selection(video: Video, clip_id: str) -> dict:
    metadata = video.video_metadata or {}
    clip_entries = list(metadata.get("clips") or [])
    if not clip_entries:
        raise InferenceServiceError("Video has no clip metadata; preprocess the video first")

    segment_number = _parse_clip_identifier(clip_id, video.id)
    matched_entry = None
    matched_index = None
    for idx, entry in enumerate(clip_entries, start=1):
        entry_segment = entry.get("segment") or idx
        if entry_segment == segment_number:
            matched_entry = entry
            matched_index = entry_segment
            break

    if not matched_entry:
        raise InferenceServiceError(f"Clip segment {segment_number} not found for video {video.id}")

    raw_path = matched_entry.get("path") or ""
    clip_path = Path(raw_path)
    if not clip_path.is_absolute():
        base = Path(video.storage_path or video.original_path or "").resolve().parent
        clip_path = (base / clip_path).resolve()
    if not clip_path.is_file():
        raise InferenceServiceError(f"Clip file not found: {clip_path}")

    start = matched_entry.get("start")
    end = matched_entry.get("end")
    duration = None
    if start is not None and end is not None:
        duration = max(0.0, float(end) - float(start))

    original_name = metadata.get("original_filename") or Path(video.storage_path or video.original_path or "").name
    label = f"{original_name} · Clip {matched_index} ({_format_clock(start)} → {_format_clock(end)})"

    return {
        "id": f"{video.id}-{matched_index}",
        "segment": matched_index,
        "path": str(clip_path),
        "start": start,
        "end": end,
        "duration": duration,
        "label": label,
        "video_id": video.id,
    }


class ClarifaiClient:
    """Lightweight Clarifai wrapper with a deterministic fallback stub."""

    def __init__(self) -> None:
        self.pat = os.getenv("CLARIFAI_PAT")
        self.user_id = os.getenv("CLARIFAI_USER_ID")
        self.app_id = os.getenv("CLARIFAI_APP_ID")
        self._real_model = None
        try:
            from clarifai.client.model import Model  # type: ignore

            self._model_cls = Model
        except Exception:  # pragma: no cover - SDK optional for tests
            self._model_cls = None

        self._client_cache: dict[str, object] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._model_cls and self.pat)

    def _get_model(self, model_id: str):
        if model_id in self._client_cache:
            return self._client_cache[model_id]
        if not self.enabled:
            raise InferenceServiceError("Clarifai SDK not configured; using stub mode")
        model = self._model_cls(
            model_id,
            pat=self.pat,
            user_id=self.user_id,
            app_id=self.app_id,
        )
        self._client_cache[model_id] = model
        return model

    def run_models(
        self,
        frames: Iterable[FrameSample],
        model_ids: list[str],
        params: InferenceParams,
    ) -> list[dict]:
        results: list[dict] = []
        frame_list = list(frames)
        for model_id in model_ids:
            if self.enabled:
                results.extend(self._run_model_real(frame_list, model_id, params))
            else:
                results.extend(self._run_model_stub(frame_list, model_id))
        return results

    def _run_model_real(
        self,
        frames: list[FrameSample],
        model_id: str,
        params: InferenceParams,
    ) -> list[dict]:
        model = self._get_model(model_id)
        detections: list[dict] = []
        for frame in frames:
            try:
                response = model.predict_by_bytes(  # type: ignore[attr-defined]
                    frame.payload,
                    input_type="image",
                    inference_params={
                        "max_concepts": params.max_concepts,
                        "min_value": params.min_confidence,
                    },
                )
            except Exception as exc:  # pragma: no cover - network failure
                logger.error("Clarifai inference failed for model %s: %s", model_id, exc)
                raise InferenceServiceError(str(exc)) from exc

            outputs = getattr(response, "outputs", []) or []
            if not outputs:
                continue
            primary = outputs[0]
            regions = getattr(getattr(primary, "data", None), "regions", None)
            concepts = getattr(getattr(primary, "data", None), "concepts", None)

            if regions:
                detections.extend(
                    self._parse_region_detections(regions, frame, model_id, params)
                )
            elif concepts:
                detections.extend(
                    self._parse_concept_detections(concepts, frame, model_id, params)
                )
        return detections

    def _parse_region_detections(self, regions, frame: FrameSample, model_id: str, params: InferenceParams):
        parsed: list[dict] = []
        for region in regions:
            bbox_obj = getattr(getattr(region, "region_info", None), "bounding_box", None)
            bbox = {
                "top": getattr(bbox_obj, "top", 0.0),
                "left": getattr(bbox_obj, "left", 0.0),
                "bottom": getattr(bbox_obj, "bottom", 0.0),
                "right": getattr(bbox_obj, "right", 0.0),
            }
            region_concepts = getattr(getattr(region, "data", None), "concepts", []) or []
            for concept in region_concepts:
                confidence = float(getattr(concept, "value", 0.0))
                if confidence < params.min_confidence:
                    continue
                parsed.append(
                    {
                        "frame_index": frame.index,
                        "timestamp_seconds": frame.timestamp_seconds,
                        "model_id": model_id,
                        "label": getattr(concept, "name", ""),
                        "confidence": confidence,
                        "bbox": bbox,
                    }
                )
        return parsed

    def _parse_concept_detections(self, concepts, frame: FrameSample, model_id: str, params: InferenceParams):
        parsed: list[dict] = []
        for concept in concepts:
            confidence = float(getattr(concept, "value", 0.0))
            if confidence < params.min_confidence:
                continue
            parsed.append(
                {
                    "frame_index": frame.index,
                    "timestamp_seconds": frame.timestamp_seconds,
                    "model_id": model_id,
                    "label": getattr(concept, "name", ""),
                    "confidence": confidence,
                    "bbox": None,
                }
            )
        return parsed

    def _run_model_stub(self, frames: list[FrameSample], model_id: str) -> list[dict]:
        detections: list[dict] = []
        for frame in frames:
            if frame.index % 2 != 0:
                continue
            confidence = 0.55 + ((hash((model_id, frame.index)) % 40) / 100.0)
            detections.append(
                {
                    "frame_index": frame.index,
                    "timestamp_seconds": frame.timestamp_seconds,
                    "model_id": model_id,
                    "label": f"{model_id}-detected",
                    "confidence": round(min(confidence, 0.99), 4),
                    "bbox": {
                        "top": 0.2,
                        "left": 0.2,
                        "bottom": 0.7,
                        "right": 0.7,
                    },
                }
            )
        return detections


def run_inference(video: Video, request: InferenceRequest) -> InferenceRun:
    """Execute Clarifai inference for the given video using request settings."""
    params_dict = request.params.dict()
    clip_info: dict | None = None
    source_override: str | None = None
    if request.clip_id:
        clip_info = _resolve_clip_selection(video, request.clip_id)
        source_override = clip_info["path"]
        params_dict["clip_id"] = clip_info["id"]

    inference_run = InferenceRun(
        project_id=video.project_id,
        video_id=video.id,
        model_ids=request.model_ids,
        params=params_dict,
        status="running",
    )
    db.session.add(inference_run)
    db.session.commit()
    logger.info(
        "Inference run started (run_id=%s, video_id=%s, models=%s, clip=%s)",
        inference_run.id,
        video.id,
        request.model_ids,
        clip_info["id"] if clip_info else "full-video",
    )
    running_payload = {"run_id": inference_run.id, "status": "running", "video_id": video.id}
    if clip_info:
        running_payload["clip_id"] = clip_info["id"]
    _emit_status("inference_status", running_payload)

    client = ClarifaiClient()
    try:
        frames = sample_frames(video, request.params.fps, source_override=source_override)
        detections = client.run_models(frames, request.model_ids, request.params)
        _persist_detections(inference_run, detections)
        _finalize_inference_run(inference_run, detections, frames, clip_info)
    except Exception as exc:
        db.session.rollback()
        inference_run.status = "failed"
        failure_payload = {"error": str(exc)}
        if clip_info:
            failure_payload["clip"] = clip_info
        inference_run.results = failure_payload
        db.session.commit()
        logger.error("Inference run %s failed: %s", inference_run.id, exc)
        failed_status = {"run_id": inference_run.id, "status": "failed", "video_id": video.id}
        if clip_info:
            failed_status["clip_id"] = clip_info["id"]
        _emit_status("inference_status", failed_status)
        raise

    completed_payload = {"run_id": inference_run.id, "status": "completed", "video_id": video.id}
    if clip_info:
        completed_payload["clip_id"] = clip_info["id"]
    _emit_status("inference_status", completed_payload)
    logger.debug(
        "Inference completed (run_id=%s, detections=%s)",
        inference_run.id,
        len(detections),
    )
    return inference_run


def _persist_detections(inference_run: InferenceRun, detections: list[dict]) -> None:
    for payload in detections:
        detection = Detection(
            inference_run_id=inference_run.id,
            frame_index=payload.get("frame_index"),
            timestamp_seconds=payload.get("timestamp_seconds"),
            model_id=payload.get("model_id"),
            label=payload.get("label"),
            confidence=payload.get("confidence"),
            bbox=payload.get("bbox") or {},
        )
        db.session.add(detection)
    logger.debug(
        "Persisting %s detection(s) for run_id=%s",
        len(detections),
        inference_run.id,
    )


def _finalize_inference_run(
    inference_run: InferenceRun,
    detections: list[dict],
    frames: list[FrameSample],
    clip: dict | None = None,
) -> None:
    model_summary: dict[str, dict] = {}
    for payload in detections:
        model_id = payload["model_id"]
        model_entry = model_summary.setdefault(model_id, {"detections": 0, "avg_confidence": 0.0})
        model_entry["detections"] += 1
        model_entry["avg_confidence"] += payload.get("confidence", 0.0)

    for model_id, summary in model_summary.items():
        count = summary["detections"]
        if count:
            summary["avg_confidence"] = round(summary["avg_confidence"] / count, 4)

    inference_run.results = {
        "frames_sampled": len(frames),
        "detections": detections,
        "models": model_summary,
        "scope": "clip" if clip else "video",
    }
    if clip:
        inference_run.results["clip"] = clip
    inference_run.status = "completed"
    billing_service.apply_run_cost(inference_run, len(frames))
    db.session.commit()

