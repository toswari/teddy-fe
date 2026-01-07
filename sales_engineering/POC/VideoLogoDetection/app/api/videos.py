"""Videos API blueprint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from marshmallow import Schema, ValidationError, fields

from app.models import Project, Video
from app.services import video_service, inference_service

bp = Blueprint("videos", __name__, url_prefix="/api/videos")


class VideoCreateSchema(Schema):
    project_id = fields.Int(required=True)
    source_path = fields.Str(required=True)


video_create_schema = VideoCreateSchema()


@bp.post("")
def upload_video():
    try:
        payload = video_create_schema.load(request.json)
    except ValidationError as err:
        return {"errors": err.messages}, 400

    Project.query.get_or_404(payload["project_id"])
    video = video_service.register_video(payload["project_id"], payload["source_path"])
    metadata = video_service.probe_video_metadata(video)
    clips = video_service.generate_clips(video)
    return {
        "video_id": video.id,
        "metadata": metadata,
        "clips": [str(path) for path in clips],
    }, 201


@bp.post("/<int:video_id>/inference")
def run_inference(video_id: int):
    video = Video.query.get_or_404(video_id)
    data = request.get_json(silent=True) or {}
    model_ids = data.get("model_ids", ["general-image-recognition"])
    inference_run = inference_service.run_inference(video, model_ids)
    return jsonify({"inference_run_id": inference_run.id, "status": inference_run.status})
