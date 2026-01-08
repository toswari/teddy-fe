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
from flask import current_app

logger = logging.getLogger(__name__)


class InferenceServiceError(RuntimeError):
    """Raised when Clarifai inference fails."""


@dataclass
class FrameSample:
    index: int
    timestamp_seconds: float
    payload: bytes


def _batched_frames(frames: list[FrameSample], batch_size: int) -> Iterable[list[FrameSample]]:
    size = max(1, int(batch_size or 1))
    for start in range(0, len(frames), size):
        yield frames[start : start + size]


def _emit_status(event: str, payload: dict) -> None:
    """Emit Socket.IO status messages without breaking on failure."""
    try:
        socketio.emit(event, payload)
    except Exception:  # pragma: no cover - socket errors should not kill request
        logger.debug("SocketIO emit failed for event=%s", event, exc_info=True)


def get_frame_image_path(video: Video, run_id: int, frame_index: int) -> Path:
    """Return the path for a stored frame image for a given run."""
    media_root = Path(current_app.config.get("PROJECT_MEDIA_ROOT", "media"))
    frame_path = (
        media_root
        / f"project_{video.project_id}"
        / f"video_{video.id}"
        / "runs"
        / f"run_{run_id}"
        / "frames"
        / f"frame_{frame_index:04d}.jpg"
    )
    return frame_path


def sample_frames(
    video: Video,
    fps: float,
    *,
    source_override: str | None = None,
) -> List[FrameSample]:
    """Sample frames at the requested FPS and return JPEG payloads."""
    if fps <= 0:
        raise InferenceServiceError("Sampling FPS must be positive")

    source = Path(
        source_override or video.storage_path or video.original_path or ""
    )
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

    logger.debug(
        "Sampled %s frame(s) from video id=%s",
        len(samples),
        video.id,
    )
    return samples


def _store_frame_images(
    video: Video,
    inference_run: InferenceRun,
    frames: list[FrameSample],
) -> list[dict]:
    """Persist sampled frames as JPEGs and return lightweight metadata."""
    frame_records: list[dict] = []
    for frame in frames:
        frame_path = get_frame_image_path(video, inference_run.id, frame.index)
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(frame_path, "wb") as outfile:
                outfile.write(frame.payload)
        except OSError as exc:  # pragma: no cover - filesystem failures rare
            logger.warning(
                "Failed to persist frame %s for run %s: %s",
                frame.index,
                inference_run.id,
                exc,
            )
            continue
        frame_records.append(
            {
                "index": frame.index,
                "timestamp_seconds": round(float(frame.timestamp_seconds or 0.0), 4),
                "image_path": str(frame_path),
            }
        )
    return frame_records


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
                logger.debug(
                    "Clip identifier video mismatch: expected %s, got %s",
                    video_id,
                    prefix_id,
                )
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
        raise InferenceServiceError(
            "Video has no clip metadata; preprocess the video first"
        )

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
        raise InferenceServiceError(
            f"Clip segment {segment_number} not found for video {video.id}"
        )

    raw_path = matched_entry.get("path") or ""
    clip_path = Path(raw_path)
    if not clip_path.is_absolute():
        base = Path(
            video.storage_path or video.original_path or ""
        ).resolve().parent
        clip_path = (base / clip_path).resolve()
    if not clip_path.is_file():
        raise InferenceServiceError(f"Clip file not found: {clip_path}")

    start = matched_entry.get("start")
    end = matched_entry.get("end")
    duration = None
    if start is not None and end is not None:
        duration = max(0.0, float(end) - float(start))

    original_name = metadata.get("original_filename") or Path(
        video.storage_path or video.original_path or ""
    ).name
    label = (
        f"{original_name} · Clip {matched_index} "
        f"({_format_clock(start)} -> {_format_clock(end)})"
    )

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
        # Prefer SDK helpers when available; fall back to unary or REST predict.
        detections: list[dict] = []
        inference_params = {
            "max_concepts": params.max_concepts,
            "min_value": params.min_confidence,
        }

        # Try SDK Image helper path first
        try:
            from clarifai.runners.utils.data_types import Image  # type: ignore

            model = self._get_model(model_id)
            for batch in _batched_frames(frames, params.batch_size):
                inputs = [
                    {
                        "image": Image(bytes=frame.payload),
                        "metadata": {
                            "frame_index": frame.index,
                            "timestamp_seconds": frame.timestamp_seconds,
                        },
                    }
                    for frame in batch
                ]
                try:
                    response = model.predict(  # type: ignore[attr-defined]
                        inputs=inputs,
                        inference_params=inference_params,
                    )
                except Exception as exc:  # pragma: no cover - network failure
                    logger.error("Clarifai inference failed for model %s: %s", model_id, exc)
                    raise InferenceServiceError(str(exc)) from exc

                outputs = getattr(response, "outputs", []) or []
                if not outputs:
                    continue

                for frame, output in zip(batch, outputs):
                    data = getattr(output, "data", None)
                    if data is None:
                        continue
                    regions = getattr(data, "regions", None)
                    concepts = getattr(data, "concepts", None)

                    if regions:
                        detections.extend(
                            self._parse_region_detections(regions, frame, model_id, params)
                        )
                    elif concepts:
                        detections.extend(
                            self._parse_concept_detections(concepts, frame, model_id, params)
                        )
            return detections
        except Exception:
            logger.debug("SDK Image helper not available; trying unary/REST fallback")

        # Try unary-bytes helper via SDK
        try:
            return self._run_model_real_unary(frames, model_id, params)
        except Exception:
            logger.debug("Unary SDK path failed; falling back to REST predict API")

        # REST predict fallback using requests
        try:
            import base64
            import requests

            pat = os.getenv("CLARIFAI_PAT")
            if not pat:
                raise InferenceServiceError("CLARIFAI_PAT not configured for REST fallback")

            base = os.getenv("CLARIFAI_API_BASE", "https://api.clarifai.com").rstrip("/")
            user = os.getenv("CLARIFAI_USER_ID")
            app_id = os.getenv("CLARIFAI_APP_ID")
            if user and app_id:
                url = f"{base}/v2/users/{user}/apps/{app_id}/models/{model_id}/outputs"
            else:
                url = f"{base}/v2/models/{model_id}/outputs"

            headers = {"Authorization": f"Key {pat}", "Content-Type": "application/json"}

            import time
            MAX_RETRIES = int(os.getenv("CLARIFAI_RETRIES", "3"))
            for batch in _batched_frames(frames, params.batch_size):
                inputs = []
                for frame in batch:
                    b64 = base64.b64encode(frame.payload).decode("ascii")
                    inputs.append(
                        {
                            "data": {"image": {"base64": b64}},
                            "metadata": {"frame_index": frame.index, "timestamp_seconds": frame.timestamp_seconds},
                        }
                    )

                body = {"inputs": inputs, "output_config": {"max_concepts": params.max_concepts}}
                attempt = 0
                while True:
                    attempt += 1
                    start_time = time.time()
                    try:
                        resp = requests.post(url, json=body, headers=headers, timeout=30)
                    except requests.RequestException as exc:  # pragma: no cover - network
                        logger.error("Clarifai REST predict request failed: %s", exc)
                        if attempt >= MAX_RETRIES:
                            raise InferenceServiceError(str(exc)) from exc
                        sleep_for = 2 ** attempt
                        time.sleep(sleep_for)
                        continue
                    duration = time.time() - start_time
                    from app.services.metrics_service import record_timer, increment_counter
                    record_timer("clarifai_request_duration", duration)
                    logger.info("Clarifai request completed in %.2fs, status %s", duration, resp.status_code)

                    # Handle rate limits and server errors with backoff
                    if resp.status_code == 429:
                        increment_counter("clarifai_rate_limits")
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait = int(retry_after)
                            except Exception:
                                wait = 2 ** attempt
                        else:
                            wait = 2 ** attempt
                        logger.warning("Clarifai rate limited, retrying after %s seconds", wait)
                        if attempt >= MAX_RETRIES:
                            logger.error("Clarifai REST predict error: %s %s", resp.status_code, resp.text)
                            raise InferenceServiceError("Clarifai REST predict failed: rate limited")
                        time.sleep(wait)
                        continue
                    if 500 <= resp.status_code < 600 and attempt < MAX_RETRIES:
                        increment_counter("clarifai_server_errors")
                        wait = 2 ** attempt
                        logger.warning("Clarifai server error %s, retrying after %s seconds", resp.status_code, wait)
                        time.sleep(wait)
                        continue
                    if resp.status_code >= 400:
                        increment_counter("clarifai_failures")
                        logger.error("Clarifai REST predict error: %s %s", resp.status_code, resp.text)
                        raise InferenceServiceError("Clarifai REST predict failed")
                    break

                payload = resp.json() if resp.content else {}
                outputs = payload.get("outputs") or []
                for frame, output in zip(batch, outputs):
                    data = output.get("data") or {}
                    regions = data.get("regions")
                    concepts = data.get("concepts")
                    if regions:
                        detections.extend(self._parse_region_detections(regions, frame, model_id, params))
                    elif concepts:
                        detections.extend(self._parse_concept_detections(concepts, frame, model_id, params))
            return detections
        except InferenceServiceError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error in REST fallback for Clarifai model %s: %s", model_id, exc)
            raise InferenceServiceError(str(exc)) from exc

    def _run_model_real_unary(
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

    def _parse_region_detections(
        self,
        regions,
        frame: FrameSample,
        model_id: str,
        params: InferenceParams,
    ):
        parsed: list[dict] = []
        for region in regions:
            bbox_obj = getattr(
                getattr(region, "region_info", None),
                "bounding_box",
                None,
            )
            bbox = {
                "top": getattr(bbox_obj, "top", 0.0),
                "left": getattr(bbox_obj, "left", 0.0),
                "bottom": getattr(bbox_obj, "bottom", 0.0),
                "right": getattr(bbox_obj, "right", 0.0),
            }
            region_concepts = (
                getattr(getattr(region, "data", None), "concepts", []) or []
            )
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

    def _parse_concept_detections(
        self,
        concepts,
        frame: FrameSample,
        model_id: str,
        params: InferenceParams,
    ):
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
            confidence = 0.55 + (
                (hash((model_id, frame.index)) % 40) / 100.0
            )
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
    params_dict = request.params.model_dump()
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
    running_payload = {
        "id": inference_run.id,
        "status": "running",
        "message": f"Inference started for {len(request.model_ids)} model(s)",
    }
    if clip_info:
        running_payload["message"] += f" on clip {clip_info['id']}"
    _emit_status("inference:update", running_payload)

    client = ClarifaiClient()
    try:
        # Sample frames
        _emit_status("inference:update", {"id": inference_run.id, "status": "sampling", "message": "Sampling frames"})
        frames = sample_frames(
            video,
            request.params.fps,
            source_override=source_override,
        )
        _emit_status("inference:update", {"id": inference_run.id, "status": "sampled", "message": f"Sampled {len(frames)} frames"})

        # Persist frame images
        _emit_status("inference:update", {"id": inference_run.id, "status": "storing_frames", "message": "Storing frame images"})
        frame_records = _store_frame_images(video, inference_run, frames)
        _emit_status("inference:update", {"id": inference_run.id, "status": "frames_stored", "message": f"Stored {len(frame_records)} frame images"})

        # Run models and emit partial results per batch
        detections: list[dict] = []
        model_list = request.model_ids or []
        total_batches = max(1, (len(frames) + request.params.batch_size - 1) // request.params.batch_size)
        batch_counter = 0
        for model_id in model_list:
            for batch in _batched_frames(frames, request.params.batch_size):
                batch_counter += 1
                batch_detections = client.run_models(batch, [model_id], request.params)
                detections.extend(batch_detections)
                # Emit partial detection update
                _emit_status(
                    "inference:update",
                    {
                        "id": inference_run.id,
                        "status": "processing",
                        "message": f"Processed batch {batch_counter} for model {model_id}",
                    },
                )

        # Persist and finalize
        _persist_detections(inference_run, detections, frame_records)
        _finalize_inference_run(
            inference_run,
            detections,
            frames,
            frame_records,
            clip_info,
        )
    except Exception as exc:
        db.session.rollback()
        inference_run.status = "failed"
        failure_payload = {"error": str(exc)}
        if clip_info:
            failure_payload["clip"] = clip_info
        inference_run.results = failure_payload
        db.session.commit()
        logger.error("Inference run %s failed: %s", inference_run.id, exc)
        failed_status = {
            "id": inference_run.id,
            "status": "failed",
            "message": f"Inference failed: {str(exc)}",
        }
        if clip_info:
            failed_status["message"] += f" on clip {clip_info['id']}"
        _emit_status("inference:update", failed_status)
        raise

    completed_payload = {
        "id": inference_run.id,
        "status": "completed",
        "message": f"Inference completed with {len(detections)} detections",
    }
    if clip_info:
        completed_payload["message"] += f" on clip {clip_info['id']}"
    _emit_status("inference:update", completed_payload)
    logger.debug(
        "Inference completed (run_id=%s, detections=%s)",
        inference_run.id,
        len(detections),
    )
    return inference_run


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    import time
    import random

    def wrapper(*args, **kwargs):
        attempt = 0
        while True:
            try:
                return func(*args, **kwargs)
            except InferenceServiceError:
                raise
            except Exception as exc:
                attempt += 1
                if attempt > max_retries:
                    raise
                # Exponential backoff with jitter
                delay = base_delay * (2 ** (attempt - 1))
                jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                wait = delay + jitter
                logger.warning("Retrying after exception: %s (attempt %s), waiting %s seconds", exc, attempt, wait)
                time.sleep(wait)
    return wrapper


def run_single_model_inference(frames: list[FrameSample], model_id: str, params: InferenceParams) -> list[dict]:
    """Run a single model against provided frame samples with simple retry/backoff."""
    client = ClarifaiClient()

    def _call():
        return client.run_models(frames, [model_id], params)

    return _retry_with_backoff(_call)()


def run_multi_model_inference(frames: list[FrameSample], model_ids: list[str], params: InferenceParams) -> list[dict]:
    """Run multiple models in sequence with retry/backoff per model."""
    client = ClarifaiClient()
    all_detections: list[dict] = []
    for model_id in model_ids:
        def _call(mid=model_id):
            return client.run_models(frames, [mid], params)

        detections = _retry_with_backoff(_call)()
        all_detections.extend(detections)
    return all_detections


def _persist_detections(inference_run: InferenceRun, detections: list[dict], frame_records: list[dict] | None = None) -> None:
    """Persist detections and optionally link to frame image paths from frame_records."""
    frame_map = {f["index"]: f.get("image_path") for f in (frame_records or [])}
    for payload in detections:
        frame_idx = payload.get("frame_index")
        detection = Detection(
            inference_run_id=inference_run.id,
            frame_index=frame_idx,
            timestamp_seconds=payload.get("timestamp_seconds"),
            model_id=payload.get("model_id"),
            label=payload.get("label"),
            confidence=payload.get("confidence"),
            bbox=payload.get("bbox") or {},
            frame_image_path=frame_map.get(frame_idx),
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
    frame_records: list[dict],
    clip: dict | None = None,
) -> None:
    model_summary: dict[str, dict] = {}
    for payload in detections:
        model_id = payload["model_id"]
        model_entry = model_summary.setdefault(
            model_id,
            {"detections": 0, "avg_confidence": 0.0},
        )
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
        "frames": frame_records,
        "scope": "clip" if clip else "video",
    }
    if clip:
        inference_run.results["clip"] = clip
    inference_run.status = "completed"
    billing_service.apply_run_cost(inference_run, len(frames))
    db.session.commit()

