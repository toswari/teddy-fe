"""Videos API blueprint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from marshmallow import Schema, ValidationError, fields, validate
from sqlalchemy.orm import selectinload

from app.api.schemas import DetectionSchema, InferenceRunSchema, VideoSchema
from app.extensions import db, socketio
from app.models import InferenceRun, Project, Video
from app.services import inference_service, video_service, reporting_service
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


class PreprocessRequestSchema(Schema):
    start_seconds = fields.Float(load_default=None, allow_none=True, validate=validate.Range(min=0))
    duration_seconds = fields.Float(load_default=None, allow_none=True, validate=validate.Range(min=1))
    clip_length = fields.Int(load_default=20, validate=validate.Range(min=1, max=900))


video_create_schema = VideoCreateSchema()
inference_request_schema = InferenceRequestSchema()
preprocess_request_schema = PreprocessRequestSchema()
video_schema = VideoSchema()
videos_schema = VideoSchema(many=True)
detections_schema = DetectionSchema(many=True)
inference_run_schema = InferenceRunSchema()


@bp.get("")
def list_videos(project_id: int):
    Project.query.get_or_404(project_id)
    videos = (
        Video.query.options(selectinload(Video.inference_runs))
        .filter_by(project_id=project_id)
        .order_by(Video.created_at.desc())
        .all()
    )
    return jsonify(videos_schema.dump(videos))


@bp.post("")
def upload_video(project_id: int):
    Project.query.get_or_404(project_id)
    
    # Handle file upload
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


@bp.post("/<int:video_id>/inference")
def run_inference(project_id: int, video_id: int):
    video = Video.query.get_or_404(video_id)
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    payload = request.get_json(silent=True) or {}
    try:
        data = inference_request_schema.load(payload)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    inference_request = InferenceRequest(**data)
    inference_run = inference_service.run_inference(video, inference_request)
    return inference_run_schema.dump(inference_run), 202


@bp.post("/<int:video_id>/multi-inference")
def run_multi_inference(project_id: int, video_id: int):
    video = Video.query.get_or_404(video_id)
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    payload = request.get_json(silent=True) or {}
    try:
        data = inference_request_schema.load(payload)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    inference_request = InferenceRequest(**data)
    inference_run = inference_service.run_inference(video, inference_request)
    return inference_run_schema.dump(inference_run), 202


@bp.post("/<int:video_id>/preprocess")
def preprocess_video(project_id: int, video_id: int):
    video = Video.query.get_or_404(video_id)
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    payload = request.get_json(silent=True) or {}
    try:
        options = preprocess_request_schema.load(payload)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    socketio.emit(
        "preprocess_status",
        {"video_id": video_id, "project_id": project_id, "status": "running"},
    )
    try:
        metadata = video_service.probe_video_metadata(video)
        clips = video_service.generate_clips(
            video,
            clip_length=options.get("clip_length") or 20,
            start_seconds=options.get("start_seconds"),
            duration_seconds=options.get("duration_seconds"),
        )
        socketio.emit(
            "preprocess_status",
            {"video_id": video_id, "project_id": project_id, "status": "completed"},
        )
        return {
            "video_id": video.id,
            "status": video.status,
            "video_metadata": video.video_metadata,
            "clips": [str(path) for path in clips],
        }
    except video_service.VideoProcessingError as exc:
        socketio.emit(
            "preprocess_status",
            {"video_id": video_id, "project_id": project_id, "status": "failed", "error": str(exc)},
        )
        return {"error": str(exc)}, 400


@bp.get("/<int:video_id>/status")
def get_video_status(project_id: int, video_id: int):
    video = Video.query.get_or_404(video_id)
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

    model_ids = sorted({det.model_id or "unknown" for det in inference_run.detections} or set(inference_run.model_ids or []))
    frames = {}
    for detection in inference_run.detections:
        frame_index = detection.frame_index if detection.frame_index is not None else -1
        entry = frames.setdefault(
            frame_index,
            {
                "frame_index": detection.frame_index,
                "timestamp_seconds": float(detection.timestamp_seconds or 0.0),
            },
        )
        if detection.timestamp_seconds is not None:
            entry["timestamp_seconds"] = float(detection.timestamp_seconds)

    ordered_frames = sorted(frames.values(), key=lambda item: (item["frame_index"] is None, item["frame_index"] or 0))

    return {
        "run_id": inference_run.id,
        "video_id": inference_run.video_id,
        "models": model_ids,
        "frames": ordered_frames,
        "detections": detections_schema.dump(inference_run.detections),
    }


@bp.post("/<int:video_id>/report")
def generate_video_report(project_id: int, video_id: int):
    project = Project.query.get_or_404(project_id)
    video = Video.query.get_or_404(video_id)
    if video.project_id != project_id:
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


@bp.delete("/<int:video_id>")
def delete_video(project_id: int, video_id: int):
    video = Video.query.get_or_404(video_id)
    if video.project_id != project_id:
        return {"error": "Video not in project"}, 404
    
    try:
        # Delete physical files
        if video.storage_path:
            import shutil
            from pathlib import Path
            storage_path = Path(video.storage_path)
            if storage_path.exists():
                # Delete the video file
                storage_path.unlink()
                # Try to delete the parent directory (video folder) if empty
                video_dir = storage_path.parent
                if video_dir.exists() and not any(video_dir.iterdir()):
                    video_dir.rmdir()
        
        # Delete database record (cascades to clips, detections, runs)
        db.session.delete(video)
        db.session.commit()
        
        return {"message": "Video deleted successfully"}, 200
    except Exception as exc:
        db.session.rollback()
        return {"error": f"Failed to delete video: {str(exc)}"}, 500
