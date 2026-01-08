"""Project-level business logic."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
        settings=deepcopy(DEFAULT_SETTINGS),
        budget_limit=25,
        last_opened_at=datetime.now(timezone.utc),
    )
    db.session.add(project)
    db.session.commit()
    logger.info("Seed project created (id=%s)", project.id)
    return project


def list_projects() -> Iterable[Project]:
    stmt = (
        select(Project)
        .options(
            selectinload(Project.videos),
            selectinload(Project.inference_runs),
        )
        .order_by(Project.last_opened_at.desc())
    )
    projects = db.session.execute(stmt).scalars().all()
    logger.debug("Retrieved %s projects", len(projects))
    return projects


def create_project(payload: dict) -> Project:
    project = Project(
        name=payload["name"],
        description=payload.get("description", ""),
        settings=payload.get("settings", deepcopy(DEFAULT_SETTINGS)),
        budget_limit=payload.get("budget_limit", 0),
        currency=payload.get("currency", "USD"),
    )
    db.session.add(project)
    db.session.commit()
    logger.info("Project created (id=%s, name=%s)", project.id, project.name)
    return project


def get_project(project_id: int) -> Optional[Project]:
    stmt = (
        select(Project)
        .options(
            selectinload(Project.videos),
            selectinload(Project.inference_runs),
        )
        .where(Project.id == project_id)
    )
    project = db.session.execute(stmt).scalar_one_or_none()
    logger.debug("Fetched project id=%s (found=%s)", project_id, bool(project))
    return project


def update_project(project: Project, payload: dict) -> Project:
    for key, value in payload.items():
        setattr(project, key, value)
    project.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    logger.info("Project updated (id=%s)", project.id)
    return project
