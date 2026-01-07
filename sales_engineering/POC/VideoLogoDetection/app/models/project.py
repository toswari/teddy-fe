"""Project model definition."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    settings = db.Column(JSONB().with_variant(db.JSON, "sqlite"), nullable=False, default=dict)
    budget_limit = db.Column(db.Numeric(10, 2), default=0)
    currency = db.Column(db.String(8), default="USD")
    last_opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    videos = db.relationship("Video", back_populates="project", cascade="all, delete-orphan")
    inference_runs = db.relationship(
        "InferenceRun", back_populates="project", cascade="all, delete-orphan"
    )

    def touch(self) -> None:
        self.last_opened_at = datetime.utcnow()
