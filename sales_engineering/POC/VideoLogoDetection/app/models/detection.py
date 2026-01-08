"""Detection model definition."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


class Detection(db.Model):
    __tablename__ = "detections"

    id = db.Column(db.Integer, primary_key=True)
    inference_run_id = db.Column(db.Integer, db.ForeignKey("inference_runs.id"), nullable=False, index=True)
    frame_index = db.Column(db.Integer)
    timestamp_seconds = db.Column(db.Numeric(10, 4))
    model_id = db.Column(db.String(64), index=True)
    label = db.Column(db.String(255))
    confidence = db.Column(db.Numeric(5, 4))
    bbox = db.Column(JSONB().with_variant(db.JSON, "sqlite"), nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inference_run = db.relationship("InferenceRun", back_populates="detections")

