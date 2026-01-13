# VideoLogoDetection POC

**Version:** 1.0.0

VideoLogoDetection is a single-user, forensic video analysis proof-of-concept focused on:

- Running AI-based logo/object detection on long-form videos
- Comparing multiple Clarifai models on the same footage
- Estimating and tracking analysis cost
- Managing multiple projects (cases) and resuming work on a chosen project

## Key Characteristics

- **Scope**: Single analyst, local/trusted environment, no authentication.
- **Projects**: Each project owns its own videos, inference runs, metrics, and reports.
- **Continue Project**: The UI surfaces a "continue last project" entry point based on recent activity.
- **Stack**: Python 3.11, Flask, PostgreSQL/JSONB, Clarifai, Gemini, PyAV, OpenCV, Tailwind-based UI.

## Running the Database with Podman

For this POC, only PostgreSQL runs in a container; the Flask app runs on the host and long-running work is handled in-process (no Celery/Redis).

1. Start Postgres via Podman (from this directory):
	```bash
	podman-compose up -d db
	```
	This starts Postgres 15 on host port 35432 with defaults:
	- DB_USER: videologo_user
	- DB_PASSWORD: videologo_pass
	- DB_NAME: videologo_db

2. Configure the local environment (conda + env vars):
	```bash
	./setup-env.sh
	```
	This script creates/activates the conda env, installs dependencies, and exports:
	- DB_HOST=localhost
	- DB_PORT=35432
	- DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
	- Runs `setup-database.sh` to ensure the Podman container is up and the latest schema (`create-schema.sql`) is applied.

3. Start the application (command may vary based on implementation):
	```bash
	./start.sh
	```

For detailed requirements and design, see:

- Software specification: SoftwareSpecification.md
- User guide: UserGuide.md
- Technical implementation plan: Technical Implementation Plan.md
- Technology stack details: TechnologyStack.md
- UI coding guidance: UI Coding Guidance.md
- API examples: docs/api-examples.md
- Media storage layout: docs/storage-layout.md
- Sample data loader: scripts/load_sample_data.py
- Detection overlay mock: visit `/demo/detection-overlay` in the running app to see a reference UI for drawing bounding boxes and concept badges on top of a frame.

## Exporting Run Artifacts

When reviewing detections inside the dashboard, the **Export Run** button sits next to the Frame Overlay Review run selector. The button automatically targets the currently selected run and:

1. Calls `GET /api/reports/run/<runId>/download`.
2. Streams back `run_<runId>.zip` containing:
	- `frames/frame_<frame>_overlay.png` – per-frame PNGs with model-specific bounding boxes (Model A = red `#FF0000`, Model B = dark blue `#003366`).
	- `json/model_<A|B>_frame_<frame>.json` plus optional `detections_aggregate.json`.
	- `manifest.json` summarizing run metadata, file counts, and timestamps.

Archives are written to `reports/run_<runId>.zip` on disk before downloading, so they can also be distributed manually if needed.

## Core Workflows

- **Project management**: `/api/projects` CRUD endpoints with automatic `last_opened_at` tracking and overview metrics via `/api/projects/<id>/overview`.
- **Video ingestion**: Register local videos with `/api/projects/<id>/videos`, preprocess clips, and monitor status updates streamed via Socket.IO (`preprocess_status`).
- **Inference**: Trigger single or multi-model Clarifai runs through `/api/projects/<id>/videos/<video_id>/multi-inference`. Sampling, detection persistence, and cost projections run in-process with live updates on `inference_status`.
- **Metrics & costs**: Aggregate benchmarking data through `/api/metrics/projects/<id>` or per-run analytics via `/api/metrics/inference-runs/<id>`.
- **Reporting**: Generate a minimal Word report with `/api/projects/<id>/videos/<video_id>/report`; files are written to `reports/project_<id>/`.

## Running Tests

Install dev deps (pytest) and run:

```bash
pytest
```

The fixtures boot the app in test mode with an in-memory SQLite DB so agents can quickly validate services and APIs before wiring additional features.

### Quick Local Inference Smoke Test

Need to confirm the Clarifai pipeline (frame sampling → detections → dashboard data) without touching the UI? Use the helper script that exercises the entire stack with the stubbed Clarifai client:

```bash
python scripts/run_local_inference.py \
	--video media/project_1/video_1/video_1_sample.mp4 \
	--models general-image-recognition
```

The script will:

- Create or reuse a demo project in your database
- Register/clone the supplied video, probe metadata, and create clips
- Run `InferenceRequest` end-to-end (in stub mode if `CLARIFAI_PAT` is absent)
- Print the run id plus per-model detection counts so you can immediately open `/api/projects/<project_id>/videos/<video_id>/runs/<run_id>/detections` or the dashboard comparison card

Override sampling parameters (`--fps`, `--min-confidence`, etc.) or point to a different MP4 with `--video`. Provide `CLARIFAI_PAT` (and related IDs) to hit the real API; otherwise, the deterministic stub data keeps the UI populated.

## Reference UI Mock

- Start the Flask server (`./start.sh`) and open `http://localhost:5000/demo/detection-overlay` to preview the static detection overlay example.
- The page renders Clarifai-style bounding boxes using Tailwind utility classes so future UI work can copy the structure when implementing the real video detail view.
