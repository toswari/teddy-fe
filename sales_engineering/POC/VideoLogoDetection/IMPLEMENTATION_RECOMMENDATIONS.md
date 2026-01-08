Recommendations — ImplementationTaskPlan follow-ups

These recommendations capture practical, high-value follow-ups discovered while implementing the MVP features and running tests. They are ordered by impact and ease of implementation.

1) Add an explicit DB migration for `Detection.frame_image_path`:
   - Why: The `Detection` model now stores `frame_image_path` to link detections to persisted frame JPEGs. Add an Alembic migration (or schema-init SQL) so existing deployments are upgraded safely.
   - Suggested migration (Alembic):
     - Add a nullable `frame_image_path` column (VARCHAR(1024)) to `detections`.
     - Backfill is optional; new runs will populate this field.

2) Detections API with grouped payload:
   - Why: UI model comparison and overlays require a single API that returns `models`, `frames` (with `image_url`), `detections`, and `detections_by_model` grouped by model id and ordered as requested.
   - Endpoint: `GET /projects/<project_id>/videos/<video_id>/runs/<run_id>/detections`
   - Recommended response shape:
     {
       "run_id": 123,
       "video_id": 45,
       "models": ["logo-detection-v2", "other-model"],
       "frames": [
         {"index": 0, "timestamp_seconds": 0.0, "image_url": "/media/.../frame_0000.jpg"},
         ...
       ],
       "detections": [
         {"id": 1, "frame_index": 0, "timestamp_seconds": 0.0, "model_id": "logo-detection-v2", "label": "acme", "confidence": 0.92, "bbox": {...}, "image_url": "/media/.../frame_0000.jpg"},
         ...
       ],
       "detections_by_model": {
         "logo-detection-v2": [<detection ids or objects>],
         "other-model": [...]
       }
     }
   - Notes:
     - `image_url` may be a relative path served by the Flask static/media endpoint or a signed URL if remote storage is used later.
     - Include both an ordered `models` list and a `detections_by_model` mapping for fast client rendering.

3) Add API-level pagination / limit for large runs:
   - Why: Long videos and high FPS sampling can produce many frames/detections. Provide `limit`/`offset` or a `frame_range` parameter to restrict payload size.

4) Serve media paths via a dedicated route:
   - Why: Using a dedicated `GET /media/...` route (or configuring Flask to serve `media` directory) allows later replacement with signed URLs or remote object storage with minimal client changes.

5) Index common JSONB fields and `model_id` on `detections`:
   - Why: Queries such as per-model counts, time range filtering, or ROI searches will benefit from indexing. Add an index on `detections(model_id)` (already present) and consider GIN indexes for JSONB if you plan to query inside `bbox` or other JSON fields.

6) Add tests for new endpoint and migration:
   - Unit test for the detections endpoint validating payload shape and grouping.
   - Migration test or a small schema-init check to ensure the DB accepts the new column.

Suggested small implementation tasks (next sprint):
- Implement the detections API endpoint described above and add/extend tests in `tests/test_inference_api.py`.
- Create a small Alembic migration script `versions/xxxx_add_frame_image_path_to_detections.py` that adds the column.
- Add an integration test that runs `run_inference` in stub mode, calls the detections endpoint, and asserts the payload includes `image_url` and `detections_by_model`.
- Update `README.md` / changelog noting the schema change and new API.

Quick Migration Example (Alembic):

# In Alembic migration file
#
# from alembic import op
# import sqlalchemy as sa
#
# def upgrade():
#     op.add_column('detections', sa.Column('frame_image_path', sa.String(length=1024), nullable=True))
#
# def downgrade():
#     op.drop_column('detections', 'frame_image_path')

API Spec — GET detections (example implementation notes):
- Route: `GET /projects/<project_id>/videos/<video_id>/runs/<run_id>/detections`
- Query params:
  - `limit` (int) — max number of detections to return
  - `frame_start`, `frame_end` (int) — restrict to a frame range
  - `model_id` (string, optional) — filter to a specific model
- Implementation hints:
  - Load `InferenceRun` and its `results['frames']` for frame records.
  - Query `Detection` rows for the run and join results to include `frame_image_path`.
  - Build `detections_by_model` by iterating in the order of `InferenceRun.model_ids` when present; otherwise sorted by `model_id`.
  - Return `image_url` derived from `frame_image_path` (convert to relative media path or route handler).

Updated TODO progress:
- [x] Add `frame_image_path` to `Detection` model and persist links from inference runs (code + tests completed).
- [ ] Add Alembic migration for existing DBs.
- [ ] Implement detections API and tests.
- [ ] Update README / changelog.

If you want, I can implement the `GET /projects/<project_id>/videos/<video_id>/runs/<run_id>/detections` endpoint and accompanying tests now (I'll add a focused TODO and run `pytest`).
