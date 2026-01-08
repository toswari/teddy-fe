"""Shared Marshmallow schemas for API responses."""
from __future__ import annotations

from marshmallow import Schema, fields


class IsoDateTime(fields.DateTime):
    def __init__(self, *args, **kwargs):
        super().__init__(format="iso", *args, **kwargs)


class ProjectSchema(Schema):
    id = fields.Int(required=True)
    name = fields.Str(required=True)
    description = fields.Str()
    settings = fields.Dict()
    budget_limit = fields.Float()
    currency = fields.Str()
    last_opened_at = IsoDateTime()
    created_at = IsoDateTime()
    updated_at = IsoDateTime()
    video_count = fields.Method("get_video_count")
    inference_run_count = fields.Method("get_inference_run_count")

    def get_video_count(self, obj):
        return len(getattr(obj, "videos", []))

    def get_inference_run_count(self, obj):
        return len(getattr(obj, "inference_runs", []))


class VideoSchema(Schema):
    id = fields.Int(required=True)
    project_id = fields.Int(required=True)
    original_path = fields.Str(required=True)
    storage_path = fields.Str(allow_none=True)
    duration_seconds = fields.Int(allow_none=True)
    resolution = fields.Str(allow_none=True)
    status = fields.Str()
    video_metadata = fields.Dict(attribute="video_metadata")
    created_at = IsoDateTime()
    inference_runs = fields.Nested("InferenceRunSchema", many=True, dump_only=True)


class InferenceRunSchema(Schema):
    id = fields.Int(required=True)
    project_id = fields.Int(required=True)
    video_id = fields.Int(required=True)
    model_ids = fields.List(fields.Str())
    params = fields.Dict()
    results = fields.Dict()
    cost_actual = fields.Float()
    cost_projected = fields.Float()
    efficiency_ratio = fields.Float()
    status = fields.Str()
    created_at = IsoDateTime()


class DetectionSchema(Schema):
    id = fields.Int(required=True)
    inference_run_id = fields.Int(required=True)
    frame_index = fields.Int(allow_none=True)
    timestamp_seconds = fields.Float(allow_none=True)
    model_id = fields.Str(allow_none=True)
    label = fields.Str(allow_none=True)
    confidence = fields.Float(allow_none=True)
    bbox = fields.Dict()
    created_at = IsoDateTime()
