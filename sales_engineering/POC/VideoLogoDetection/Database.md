# Database Overview

This document describes the PostgreSQL schema used by the Video Logo Detection proof of concept (aligned with Technical Implementation Plan v1.0.0) and how to provision it in the local Podman-managed database.

## Stored Data

The application persists four core entity types:

- **projects**: High-level containers that track Clarifai analysis initiatives.
- **videos**: Uploaded media assets that belong to a project.
- **inference_runs**: Execution records that capture inference results for a specific video (optionally with multiple models).
- **detections**: Individual detections emitted by inference runs, including bounding boxes per frame.

All tables use PostgreSQL identity columns for primary keys and rely on JSONB for flexible metadata payloads.

## Table Details

### projects

| Column | Type | Notes |
| --- | --- | --- |
| id | integer (identity) | Primary key |
| name | varchar(120) | Required project name |
| description | text | Optional free-form description |
| settings | jsonb | Required config blob (defaults to `{}`) |
| budget_limit | numeric(10,2) | Budget amount, defaults to 0 |
| currency | varchar(8) | ISO currency code, defaults to `USD` |
| last_opened_at | timestamptz | Defaults to current timestamp |
| created_at | timestamptz | Defaults to current timestamp |
| updated_at | timestamptz | Defaults to current timestamp (updated by the ORM) |

### videos

| Column | Type | Notes |
| --- | --- | --- |
| id | integer (identity) | Primary key |
| project_id | integer | References projects.id (cascade delete) |
| original_path | varchar(255) | Required source file path |
| storage_path | varchar(255) | Optional processed asset location |
| duration_seconds | integer | Duration metadata |
| resolution | varchar(32) | Resolution string (e.g., `1920x1080`) |
| status | varchar(32) | Must be one of `uploaded`, `processed`, `failed`; defaults to `uploaded` |
| metadata | jsonb | Arbitrary contextual details |
| created_at | timestamptz | Defaults to current timestamp |

### inference_runs

| Column | Type | Notes |
| --- | --- | --- |
| id | integer (identity) | Primary key |
| project_id | integer | References projects.id (cascade delete) |
| video_id | integer | References videos.id (cascade delete) |
| model_ids | text[] | Model identifiers used in the run |
| params | jsonb | Parameter payload |
| results | jsonb | Inference output payload |
| cost_actual | numeric(10,4) | Actual spend |
| cost_projected | numeric(10,4) | Projected spend |
| efficiency_ratio | numeric(10,4) | Efficiency metric |
| status | varchar(32) | Run status, defaults to `pending` |
| status constraint | check | Allowed values: `pending`, `running`, `completed`, `failed` |
| created_at | timestamptz | Defaults to current timestamp |

### detections

| Column | Type | Notes |
| --- | --- | --- |
| id | integer (identity) | Primary key |
| inference_run_id | integer | References inference_runs.id (cascade delete) |
| frame_index | integer | Zero-based frame index |
| timestamp_seconds | numeric(10,4) | Presentation-friendly timestamp |
| model_id | varchar(64) | Source model identifier |
| label | varchar(255) | Detection label |
| confidence | numeric(5,4) | Probability/confidence |
| bbox | jsonb | Bounding box `{x, y, w, h}` |
| created_at | timestamptz | Defaults to current timestamp |

## Relationships

- A project can have many videos; deleting a project cascades to its videos and inference runs.
- A project can have many inference runs directly.
- Each inference run belongs to both a project and a video; deleting a video cascades to its inference runs.
- Each detection belongs to a single inference run; detections cascade when their run is removed.

## Schema Initialization

1. Ensure the Podman database container is running (with the provided `podman-compose.yaml`).
2. Place the accompanying `create-schema.sql` file in the repository root (already included).
3. Run the helper script to ensure the container, database, and schema are in place: `./setup-database.sh`
	- The script defaults to `create-schema.sql`; override with `./setup-database.sh --schema-file path/to/file.sql` if needed.
4. (Optional) Reapply the schema manually if you prefer: `podman exec -i videologo_db psql -U videologo_user -d videologo_db < create-schema.sql`

The schema seeds indexes needed for per-project/video lookups and inference filtering:
- `videos.project_id`
- `inference_runs.project_id`
- `inference_runs.video_id`
- `detections.inference_run_id`
- `detections.model_id`
- `detections.timestamp_seconds`

Add JSONB indexes on `detections.bbox` or `inference_runs.results` as workloads grow (Phase 7 of the Technical Implementation Plan).

The schema installs a trigger (`trg_projects_set_updated_at`) that updates `projects.updated_at` automatically whenever the row changes.

## Maintenance Notes

- ORM-level cascade rules already replicate cascade deletes in the application; the schema also enforces them with foreign key `ON DELETE CASCADE` clauses for safety.
- `updated_at` is refreshed by SQLAlchemy on mutations; if direct SQL updates bypass the ORM, update the column manually or add a trigger if needed.
- Keep the `create-schema.sql` file in sync with any future model changes (columns, indexes, constraints).
- Consider triggers or application logic updates to maintain `projects.updated_at` when bypassing SQLAlchemy.
