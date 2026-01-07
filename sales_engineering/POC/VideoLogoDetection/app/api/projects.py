"""Projects API blueprint."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from marshmallow import Schema, ValidationError, fields

from app.extensions import db
from app.models import Project, Video, InferenceRun
from app.services import project_service

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


class ProjectCreateSchema(Schema):
    name = fields.Str(required=True)
    description = fields.Str(load_default="")
    settings = fields.Dict(load_default=dict)
    budget_limit = fields.Float(load_default=0)
    currency = fields.Str(load_default="USD")


class ProjectUpdateSchema(Schema):
    name = fields.Str()
    description = fields.Str()
    settings = fields.Dict()
    budget_limit = fields.Float()
    currency = fields.Str()


project_schema = ProjectSchema()
projects_schema = ProjectSchema(many=True)
project_create_schema = ProjectCreateSchema()
project_update_schema = ProjectUpdateSchema()


@bp.get("")
def list_projects():
    projects = project_service.list_projects()
    return jsonify(projects_schema.dump(projects))


@bp.post("")
def create_project():
    try:
        payload = project_create_schema.load(request.json)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    project = project_service.create_project(payload)
    return project_schema.dump(project), 201


@bp.get("/<int:project_id>")
def get_project(project_id: int):
    project = Project.query.get_or_404(project_id)
    project.touch()
    db.session.commit()
    return project_schema.dump(project)


@bp.patch("/<int:project_id>")
def update_project(project_id: int):
    project = Project.query.get_or_404(project_id)
    try:
        payload = project_update_schema.load(request.json, partial=True)
    except ValidationError as err:
        return {"errors": err.messages}, 400
    for key, value in payload.items():
        setattr(project, key, value)
    project.updated_at = datetime.utcnow()
    db.session.commit()
    return project_schema.dump(project)


@bp.get("/<int:project_id>/overview")
def get_project_overview(project_id: int):
    project = Project.query.get_or_404(project_id)
    video_count = Video.query.filter_by(project_id=project_id).count()
    inference_run_count = InferenceRun.query.filter_by(project_id=project_id).count()
    last_inference = InferenceRun.query.filter_by(project_id=project_id).order_by(InferenceRun.created_at.desc()).first()
    last_activity = last_inference.created_at if last_inference else project.last_opened_at
    return {
        "project_id": project.id,
        "name": project.name,
        "video_count": video_count,
        "inference_run_count": inference_run_count,
        "last_activity": last_activity.isoformat() if last_activity else None,
    }
