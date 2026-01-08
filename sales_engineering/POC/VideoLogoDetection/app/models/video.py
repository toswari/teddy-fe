"""Video model definition."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class Video(db.Model):
    __tablename__ = "videos"
    __mapper_args__ = {"eager_defaults": True}

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    original_path = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(255), nullable=True)
    duration_seconds = db.Column(db.Integer)
    resolution = db.Column(db.String(32))
    status = db.Column(db.String(32), default="uploaded")
    video_metadata = db.Column("metadata", JSONB().with_variant(db.JSON, "sqlite"), default=dict, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="videos")
    inference_runs = db.relationship("InferenceRun", back_populates="video")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('uploaded', 'processed', 'failed')",
            name="ck_videos_status",
        ),
    )
