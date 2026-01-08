"""InferenceRun model definition."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class InferenceRun(db.Model):
    __tablename__ = "inference_runs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False, index=True)
    model_ids = db.Column(db.ARRAY(db.String).with_variant(db.JSON, "sqlite"), default=list)
    params = db.Column(JSONB().with_variant(db.JSON, "sqlite"), default=dict)
    results = db.Column(JSONB().with_variant(db.JSON, "sqlite"), default=dict)
    cost_actual = db.Column(db.Numeric(10, 4), default=0)
    cost_projected = db.Column(db.Numeric(10, 4), default=0)
    efficiency_ratio = db.Column(db.Numeric(10, 4), default=0)
    status = db.Column(db.String(32), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", back_populates="inference_runs")
    video = db.relationship("Video", back_populates="inference_runs")
    detections = db.relationship(
        "Detection",
        back_populates="inference_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_inference_runs_status",
        ),
    )
