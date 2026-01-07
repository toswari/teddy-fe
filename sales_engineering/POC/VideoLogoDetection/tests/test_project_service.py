"""Unit tests for project_service."""
from __future__ import annotations

from app.services import project_service


def test_ensure_seed_project_idempotent(app):
    first = project_service.ensure_seed_project()
    second = project_service.ensure_seed_project()
    assert first.id == second.id


def test_create_project_persists(app):
    payload = {"name": "Test", "description": "Sample"}
    project = project_service.create_project(payload)
    assert project.id is not None
    assert project.name == "Test"
