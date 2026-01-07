"""Projects API blueprint."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from marshmallow import Schema, ValidationError, fields

from app.extensions import db
from app.models import Project
from app.services import project_service

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


class ProjectSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str(load_default="")
    settings = fields.Dict(load_default=dict)
    budget_limit = fields.Float(load_default=0)
    currency = fields.Str(load_default="USD")
    last_opened_at = fields.DateTime(dump_only=True)


project_schema = ProjectSchema()
projects_schema = ProjectSchema(many=True)


@bp.get("")
def list_projects():
    projects = project_service.list_projects()
    return jsonify(projects_schema.dump(projects))


@bp.post("")
def create_project():
    try:
        payload = project_schema.load(request.json)
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
