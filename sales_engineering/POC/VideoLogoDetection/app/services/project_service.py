"""Project-level business logic."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

from sqlalchemy import select

from app.extensions import db
from app.models import Project
logger = logging.getLogger(__name__)



DEFAULT_SETTINGS = {
    "fps": 1,
    "clip_length": 20,
    "models": ["general-image-recognition"],
}


def ensure_seed_project() -> Project:
    project = db.session.execute(select(Project).limit(1)).scalar_one_or_none()
    if project:
        logger.debug("Seed project already present (id=%s)", project.id)
        return project
    project = Project(
        name="Sample Project",
        description="Reference project seeded for developers.",
        settings=DEFAULT_SETTINGS,
        budget_limit=25,
        last_opened_at=datetime.utcnow(),
    )
    db.session.add(project)
    db.session.commit()
    logger.info("Seed project created (id=%s)", project.id)
    return project


def list_projects() -> Iterable[Project]:
    projects = Project.query.order_by(Project.last_opened_at.desc()).all()
    logger.debug("Retrieved %s projects", len(projects))
    return projects


def create_project(payload: dict) -> Project:
    project = Project(
        name=payload["name"],
        description=payload.get("description", ""),
        settings=payload.get("settings", DEFAULT_SETTINGS),
        budget_limit=payload.get("budget_limit", 0),
        currency=payload.get("currency", "USD"),
    )
    db.session.add(project)
    db.session.commit()
    logger.info("Project created (id=%s, name=%s)", project.id, project.name)
    return project
