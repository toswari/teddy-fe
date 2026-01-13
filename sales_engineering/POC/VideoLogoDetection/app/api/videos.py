"""Videos API blueprint."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, url_for, current_app
from marshmallow import Schema, ValidationError, fields, validate
from sqlalchemy.orm import selectinload

from app.api.schemas import DetectionSchema, InferenceRunSchema, VideoSchema
from app.extensions import db, socketio
from app.models import InferenceRun, Project, Video
from app.services import reporting_service
from app.services.reporting_service import ReportExportError
from app.services.metrics_service import summarize_run_models
from app.services.inference_models import InferenceRequest

bp = Blueprint("videos", __name__, url_prefix="/api/projects/<int:project_id>/videos")


class VideoCreateSchema(Schema):
    source_path = fields.Str(required=True)


class InferenceParamsSchema(Schema):
    fps = fields.Float(load_default=1.0)
    min_confidence = fields.Float(load_default=0.2)
    max_concepts = fields.Int(load_default=5)
    batch_size = fields.Int(load_default=8)


class InferenceRequestSchema(Schema):
    model_ids = fields.List(fields.Str(), load_default=list)
    params = fields.Nested(InferenceParamsSchema, load_default=dict)
    note = fields.Str(allow_none=True, load_default=None)
    clip_id = fields.Str(load_default=None, allow_none=True)


class PreprocessRequestSchema(Schema):
    start_seconds = fields.Float(load_default=None, allow_none=True, validate=validate.Range(min=0))
    duration_seconds = fields.Float(load_default=None, allow_none=True, validate=validate.Range(min=1))
    clip_length = fields.Int(load_default=20, validate=validate.Range(min=1, max=900))
    # New field for multiple clip segments
    clips = fields.List(fields.Dict(keys=fields.Str(), values=fields.Float()), load_default=None, allow_none=True)


video_create_schema = VideoCreateSchema()
inference_request_schema = InferenceRequestSchema()
preprocess_request_schema = PreprocessRequestSchema()
video_schema = VideoSchema()
videos_schema = VideoSchema(many=True)
detections_schema = DetectionSchema(many=True)
inference_run_schema = InferenceRunSchema()


def _reports_root() -> Path:
    base = current_app.config.get("REPORTS_ROOT")
    if base:
        return Path(base)
    return Path(current_app.root_path).parent / "reports"


@bp.get("")
def list_videos(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return {"error": "Project not found"}, 404
    videos = (
        Video.query.options(selectinload(Video.inference_runs))
        .filter_by(project_id=project_id)
        .order_by(Video.created_at.desc())
        .all()
    )
    return jsonify(videos_schema.dump(videos))


@bp.post("")
def upload_video(project_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return {"error": "Project not found"}, 404
    
    # Handle file upload
    # Local import to avoid importing heavy native deps at module import time
    from app.services import video_service

    if 'video' in request.files:
        video_file = request.files['video']
        if not video_file.filename:
            return {"error": "No file selected"}, 400
        
        try:
            video = video_service.register_uploaded_video(project_id, video_file)
            video_service.probe_video_metadata(video)
            clips = video_service.generate_clips(video)
        except video_service.VideoProcessingError as exc:
            return {"error": str(exc)}, 400
    # Handle path-based registration (backward compatibility)
    else:
        try:
            payload = video_create_schema.load(request.json)
        except ValidationError as err:
            return {"errors": err.messages}, 400

        try:
            video = video_service.register_video(project_id, payload["source_path"])
            video_service.probe_video_metadata(video)
            clips = video_service.generate_clips(video)
        except video_service.VideoProcessingError as exc:
            return {"error": str(exc)}, 400

    response = video_schema.dump(video)
    response["video_metadata"] = video.video_metadata
    response["clips"] = [str(path) for path in clips]
    return response, 201


@bp.delete("/<int:video_id>")
def delete_video_endpoint(project_id: int, video_id: int):
    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not found"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    
    # Local import
    from app.services import video_service
    
    try:
        video_service.delete_video(video)
        db.session.commit()
        return {"message": "Video deleted"}, 200
    except Exception as exc:
        db.session.rollback()
        return {"error": str(exc)}, 500


@bp.post("/<int:video_id>/inference")
def run_inference(project_id: int, video_id: int):
    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not found"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    payload = request.get_json(silent=True) or {}
    try:
        data = inference_request_schema.load(payload)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    inference_request = InferenceRequest(**data)

    # Store inference params and include clip_id if provided
    params_dict = inference_request.params.model_dump()
    if inference_request.clip_id:
        params_dict["clip_id"] = inference_request.clip_id

    # Create the inference run record first
    inference_run = InferenceRun(
        project_id=project_id,
        video_id=video_id,
        model_ids=inference_request.model_ids,
        params=params_dict,
        status="pending",
    )
    db.session.add(inference_run)
    db.session.commit()

    from app.extensions import task_queue
    from app.tasks import run_inference_task

    # Enqueue the task
    job = task_queue.enqueue(run_inference_task, inference_run.id)

    return {
        "id": inference_run.id,
        "run_id": inference_run.id,
        "status": "pending",
        "job_id": job.id,
    }, 202


@bp.post("/<int:video_id>/multi-inference")
def run_multi_inference(project_id: int, video_id: int):
    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not found"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    payload = request.get_json(silent=True) or {}
    try:
        data = inference_request_schema.load(payload)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    inference_request = InferenceRequest(**data)
    from app.services import inference_service

    try:
        inference_run = inference_service.run_inference(video, inference_request)
    except inference_service.InferenceServiceError as exc:
        return {"error": str(exc)}, 400
    return inference_run_schema.dump(inference_run), 202


@bp.post("/<int:video_id>/preprocess")
def preprocess_video(project_id: int, video_id: int):
    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not found"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    payload = request.get_json(silent=True) or {}
    try:
        options = preprocess_request_schema.load(payload)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    
    from app.extensions import task_queue
    from app.tasks import preprocess_video_task
    
    # Enqueue the task
    job = task_queue.enqueue(preprocess_video_task, video_id, options)
    
    socketio.emit(
        "preprocess:update",
        {"id": video_id, "status": "queued", "message": "Preprocessing queued"},
    )
    return {
        "video_id": video.id,
        "status": "queued",
        "job_id": job.id,
    }, 202


@bp.get("/<int:video_id>/status")
def get_video_status(project_id: int, video_id: int):
    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not found"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    inference_runs = InferenceRun.query.filter_by(video_id=video_id).all()
    return {
        "video_id": video.id,
        "status": video.status,
        "storage_path": video.storage_path,
        "video_metadata": video.video_metadata,
        "duration_seconds": video.duration_seconds,
        "resolution": video.resolution,
        "inference_runs": [inference_run_schema.dump(run) for run in inference_runs],
    }


@bp.get("/<int:video_id>/runs/<int:run_id>/detections")
def list_run_detections(project_id: int, video_id: int, run_id: int):
    inference_run = (
        InferenceRun.query.options(selectinload(InferenceRun.detections))
        .filter_by(id=run_id, video_id=video_id, project_id=project_id)
        .first()
    )
    if inference_run is None:
        return {"error": "Inference run not found for video"}, 404

    ordered_model_ids, detection_counts = summarize_run_models(inference_run)

    detections_by_model: dict[str, list] = {model_id: [] for model_id in ordered_model_ids}

    frame_metadata = (inference_run.results or {}).get("frames") or []
    frames_map: dict[int, dict] = {}

    for frame in frame_metadata:
        raw_index = frame.get("index")
        frame_index = int(raw_index) if raw_index is not None else -1
        entry = frames_map.setdefault(
            frame_index,
            {
                "frame_index": raw_index if raw_index is not None else None,
                "timestamp_seconds": float(frame.get("timestamp_seconds") or 0.0),
            },
        )
        entry["timestamp_seconds"] = float(frame.get("timestamp_seconds") or entry.get("timestamp_seconds") or 0.0)
        if frame_index >= 0:
            entry["image_url"] = url_for(
                "videos.get_run_frame",
                project_id=project_id,
                video_id=video_id,
                run_id=run_id,
                frame_index=frame_index,
            )

    for detection in inference_run.detections:
        frame_index = detection.frame_index if detection.frame_index is not None else -1
        entry = frames_map.setdefault(
            frame_index,
            {
                "frame_index": detection.frame_index,
                "timestamp_seconds": float(detection.timestamp_seconds or 0.0),
            },
        )
        if detection.timestamp_seconds is not None:
            entry["timestamp_seconds"] = float(detection.timestamp_seconds)
        if frame_index >= 0 and "image_url" not in entry:
            entry["image_url"] = url_for(
                "videos.get_run_frame",
                project_id=project_id,
                video_id=video_id,
                run_id=run_id,
                frame_index=frame_index,
            )
        target_model = detection.model_id or "unknown"
        detections_by_model.setdefault(target_model, []).append(detection)

    ordered_frames = sorted(
        frames_map.values(),
        key=lambda item: (
            item.get("frame_index") is None,
            item.get("frame_index") if item.get("frame_index") is not None else 0,
        ),
    )

    overlays_root = _reports_root() / f"run_{run_id}" / "frames"
    overlay_meta = (inference_run.results or {}).get("vlm_overlays") or {}
    overlay_model_id = overlay_meta.get("model_id")
    overlay_frames_meta = overlay_meta.get("frames") or {}
    overlay_frames_payload: dict[str, dict[str, str]] = {}

    for entry in ordered_frames:
        frame_index = entry.get("frame_index")
        if frame_index is None or frame_index < 0:
            continue
        overlay_file = overlays_root / f"frame_{int(frame_index):06}_overlay.png"
        if not overlay_file.is_file():
            continue
        overlay_url = url_for(
            "videos.get_vlm_overlay",
            project_id=project_id,
            video_id=video_id,
            run_id=run_id,
            frame_index=int(frame_index),
        )
        entry["vlm_overlay_url"] = overlay_url
        frame_key = str(frame_index)
        frame_meta = overlay_frames_meta.get(frame_key, {}) if isinstance(overlay_frames_meta, dict) else {}
        payload_entry = {"url": overlay_url}
        json_path = frame_meta.get("json_path") if isinstance(frame_meta, dict) else None
        if json_path:
            payload_entry["json_path"] = str(json_path)
        overlay_frames_payload[frame_key] = payload_entry

    payload = {
        "run_id": inference_run.id,
        "video_id": inference_run.video_id,
        "models": ordered_model_ids,
        "available_models": ordered_model_ids,
        "model_detection_counts": detection_counts,
        "params": inference_run.params or {},
        "frames": ordered_frames,
        "detections": detections_schema.dump(inference_run.detections),
        "detections_by_model": {
            model_id: detections_schema.dump(detections_by_model.get(model_id, []))
            for model_id in ordered_model_ids
        },
        "clip": (inference_run.results or {}).get("clip"),
    }
    payload["vlm_overlays"] = {
        "model_id": overlay_model_id,
        "frames": overlay_frames_payload,
    }
    current_app.logger.debug(
        "Prepared run payload (run_id=%s, models=%s, frames=%s)",
        inference_run.id,
        ordered_model_ids,
        len(ordered_frames),
    )
    return payload


@bp.get("/<int:video_id>/runs/<int:run_id>/frames/<int:frame_index>")
def get_run_frame(project_id: int, video_id: int, run_id: int, frame_index: int):
    if frame_index < 0:
        return {"error": "Frame index must be non-negative"}, 400

    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not in project"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404

    InferenceRun.query.filter_by(id=run_id, video_id=video_id, project_id=project_id).first_or_404()

    from app.services import inference_service

    frame_path = inference_service.get_frame_image_path(video, run_id, frame_index)
    if not frame_path.is_file():
        return {"error": "Frame not found"}, 404

    return send_file(frame_path, mimetype="image/jpeg")


@bp.get("/<int:video_id>/runs/<int:run_id>/vlm/overlays/<int:frame_index>")
def get_vlm_overlay(project_id: int, video_id: int, run_id: int, frame_index: int):
    if frame_index < 0:
        return {"error": "Frame index must be non-negative"}, 400

    video = db.session.get(Video, video_id)
    if video is None:
        return {"error": "Video not in project"}, 404
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404

    InferenceRun.query.filter_by(id=run_id, video_id=video_id, project_id=project_id).first_or_404()

    overlay_path = _reports_root() / f"run_{run_id}" / "frames" / f"frame_{frame_index:06}_overlay.png"
    if not overlay_path.is_file():
        return {"error": "Overlay not found"}, 404

    return send_file(overlay_path, mimetype="image/png")


@bp.get("/<int:video_id>/runs/<int:run_id>/export")
def export_run_archive(project_id: int, video_id: int, run_id: int):
    regenerate = request.args.get("regenerate", "false").lower() == "true"

    run = (
        InferenceRun.query.filter_by(id=run_id, video_id=video_id, project_id=project_id)
        .options(selectinload(InferenceRun.detections))
        .first()
    )
    if run is None:
        return {"error": "Inference run not found for video"}, 404
    if run.status != "completed":
        return {"error": "Inference run is not completed yet."}, 409

    try:
        archive_path = reporting_service.build_run_export(run, regenerate=regenerate)
    except ReportExportError as exc:
        return {"error": str(exc)}, 400
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Run export build failed (run_id=%s)", run_id, exc_info=exc)
        return {"error": "Failed to build run export."}, 500

    if not archive_path.is_file():
        return {"error": "Run export not found."}, 404

    return send_file(
        str(archive_path),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"run_{run_id}.zip",
    )


@bp.post("/<int:video_id>/report")
def generate_video_report(project_id: int, video_id: int):
    project = db.session.get(Project, project_id)
    if project is None:
        return {"error": "Project not found"}, 404
    video = db.session.get(Video, video_id)
    if video is None or video.project_id != project_id:
        return {"error": "Video not in project"}, 404

    payload = request.get_json(silent=True) or {}
    inference_run_id = payload.get("inference_run_id")
    inference_run = None
    if inference_run_id is not None:
        inference_run = InferenceRun.query.filter_by(id=inference_run_id, video_id=video_id).first()
        if inference_run is None:
            return {"error": "Inference run not found for video"}, 404

    report_path = reporting_service.generate_video_report(project, video, inference_run)
    return {"report_path": str(report_path)}, 201
