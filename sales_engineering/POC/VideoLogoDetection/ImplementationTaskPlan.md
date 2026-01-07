# Implementation Task Plan – VideoLogoDetection

**Version:** 1.0.0

This document is written for a **coding agent** implementing the VideoLogoDetection POC. It breaks the work into phases aligned with SoftwareSpecification.md and Technical Implementation Plan.md.

- Treat **Phase 1 + Phase 2** as the MVP scope. These require detailed implementation.
- Phases 3–4 are expressed as higher-level checklists for later iteration.
- Use Git commits or your own checklist to mark `- [x]` items as completed.

---

## Conventions

- All tasks assume you are working in `sales_engineering/POC/VideoLogoDetection`.
- Always ensure `setup-env.sh` and `podman-compose.yaml` remain the **single source of truth** for DB connection details.
- The app must remain **single-user**, **local**, and **project-centric** (multiple projects, no auth).
- Long-running work (video probing, clipping, inference) should initially run **in-process**; if you introduce backgrounding, do it without Redis (e.g., simple Python threads or a lightweight in-memory queue), keeping infrastructure minimal.
- Clarifai credentials and model defaults belong in `.env` (see `.env.example`); all reference scripts and services read from there, so keep it authoritative.

### Architecture Directives (Non-Negotiable for MVP)

- Do **not** introduce Redis, Celery, or any external task broker in the MVP; all long-running work is executed in-process, with only optional lightweight in-memory/background helpers if absolutely needed.
- Containerization uses a Dockerfile for the Flask app and **Podman only for PostgreSQL**, running on a non-standard host port as defined in the spec and kept in sync between `podman-compose.yaml` and `setup-env.sh`.
- The Flask factory must not initialize Celery; any `tasks/` modules are optional helpers, not tied to an external worker infrastructure.
- If you later introduce background execution, it must remain brokerless (threads or similar) and stay within the single-user, local POC constraints.

---

## Phase 1 – MVP Core

Goal: deliver a working single-user POC that can:
- Manage projects
- Ingest videos
- Clip videos into 20s segments
- Run Clarifai single-model inference on sampled frames
- Show basic dashboard/progress
- Export a minimal Word report

### 1.1 Project Skeleton & Environment

- [x] **Create Python package structure**
  - [x] Create `app/__init__.py` implementing `create_app()` using the Application Factory pattern.
  - [x] Add `app/config.py` with a `Config` class reading from `DATABASE_URL` and other env vars.
  - [x] Ensure `create_app()` initializes:
    - [x] SQLAlchemy
    - [x] Flask-SocketIO
    - [x] Any shared utilities needed for optional background execution (but **do not** add Redis or external brokers in MVP).

- [x] **Wire environment & DB connectivity**
  - [x] Confirm the app uses `DATABASE_URL` from the environment (as set by `setup-env.sh`).
  - [x] Implement a simple health-check endpoint (`GET /health`) that verifies DB connectivity.
  - [x] Document in comments or README that DB is expected at `localhost:35432` via Podman.

### 1.2 Data Model (Core Entities)

Implement SQLAlchemy models in `app/models/`:

- [x] **Project model** (`app/models/project.py`)
  - [x] Fields: `id`, `name`, `description`, `settings` (JSONB), `budget_limit`, `currency`, `created_at`, `updated_at`, `last_opened_at`.
  - [x] Add relationship(s) to `Video` and `InferenceRun`.

- [x] **Video model** (`app/models/video.py`)
  - [x] Fields: `id`, `project_id`, `original_path`, `storage_path`, `duration_seconds`, `resolution`, `status`, `created_at`.
  - [x] Relationship back to `Project`.

- [x] **InferenceRun model** (`app/models/inference_run.py`)
  - [x] Fields: `id`, `project_id`, `video_id`, `model_ids`, `params` (JSONB), `results` (JSONB), `cost_actual`, `cost_projected`, `efficiency_ratio`, `status`, `created_at`.
  - [x] Relationship to `Project` and `Video`.

- [x] **(Optional for Phase 1) Detection model**
  - [x] Only implement if needed immediately; otherwise, defer to Phase 2.

- [x] **Migrations / schema setup**
  - [x] Provide a simple schema init script or Alembic configuration to create tables based on these models.

### 1.3 Project Management API

Implement a `api.projects` blueprint under `app/api/projects.py`:

- [x] **Routes**
  - [x] `GET /projects` – list all projects with summary info (id, name, last_opened_at, #videos).
  - [x] `POST /projects` – create a new project.
  - [x] `GET /projects/<id>` – retrieve details of a single project.
  - [x] `PATCH /projects/<id>` – update name/description/settings.

- [x] **Schemas / validation**
  - [x] Implement `ProjectCreateSchema` and `ProjectUpdateSchema` using Marshmallow.
  - [x] Ensure invalid data returns clear 4xx responses.

- [x] **Last opened tracking**
  - [x] Whenever a project is accessed from the UI (e.g., via `GET /projects/<id>` for the main dashboard), update `last_opened_at`.

### 1.4 Video Upload & Storage

Implement a `api.videos` blueprint and matching service logic.

- [x] **Endpoint for video registration/upload**
  - [x] `POST /projects/<project_id>/videos` – accept a file upload or a local path reference (for POC, either is acceptable).
  - [x] Persist a `Video` record with status `uploaded` and the original path.

- [ ] **Storage & directories**
  - [ ] Use a predictable directory under the project (e.g., `media/<project_id>/` or similar) for stored video files.
  - [ ] Ensure this directory is configurable via config/env if needed.

### 1.5 Video Pre-processing & Clipping

Implement `app/services/video_service.py` with functions that can be called either synchronously (Phase 1) or from a lightweight, in-process background executor if later introduced.

- [ ] **Metadata probing**
  - [ ] Implement `probe_video_metadata(path)` using ffmpeg-python or PyAV to get duration, resolution, etc.
  - [ ] Update the `Video` record with `duration_seconds` and `resolution`.

- [ ] **Clipping into 20s segments**
  - [ ] Implement `generate_clips(source_path, clip_length=20)` using FFmpeg `-c copy`.
  - [ ] Store clips under a structured path (e.g., `media/<project_id>/<video_id>/clips/`).
  - [ ] Optionally, track basic metadata about each clip (e.g., file name, start time) in JSONB on `Video` or a separate table.

- [ ] **Triggering pre-processing**
  - [ ] Provide an endpoint `POST /videos/<id>/preprocess` that:
    - [ ] Runs pre-processing (probe + clipping) synchronously for the MVP.
    - [ ] Optionally, if you later add a simple in-process background executor (no Redis), adapt this endpoint to enqueue work there instead of blocking.
    - [ ] Updates `Video.status` accordingly (`processed` when complete).

### 1.6 Sampling & Single-Model Inference

Implement `app/services/inference_service.py` for Clarifai integration.

- [ ] **Frame sampling**
  - [ ] Implement frame extraction using PyAV and OpenCV:
    - [ ] Fixed FPS (e.g., 1 FPS for Phase 1).
    - [ ] Optionally prepare hooks for motion-based filtering but keep Phase 1 minimal.

- [ ] **Clarifai single-model call**
  - [ ] Use the Clarifai SDK with PAT from `.env` / environment.
  - [ ] Implement `run_single_model_inference(frames, model_id, config)` that:
    - [ ] Sends frames in batches.
    - [ ] Returns normalized detection data suitable for JSONB storage.
  - [ ] Use `docs/ClarifaiAPI.md` for parameter/reference patterns and `scripts/demo_logo_detection.py` to manually verify PAT + model IDs before wiring the service.

- [ ] **Endpoint to trigger inference**
  - [ ] `POST /videos/<id>/inference` – starts an inference run for a given model.
  - [ ] Create an `InferenceRun` record with status transitions (`pending` → `running` → `completed/failed`).

### 1.7 Minimal Dashboard & Progress

Implement basic Mission Control UI/API for Phase 1.

- [ ] **API endpoints**
  - [ ] `GET /projects/<id>/overview` – aggregate basic stats (video count, runs, last activity).
  - [ ] `GET /videos/<id>/status` – return pre-processing + inference status.

- [ ] **SocketIO events (minimal)**
  - [ ] Emit events for pre-processing and inference state changes.
  - [ ] Keep payloads simple (IDs, status, message).

- [ ] **UI (front-end agent guidance)**
  - [ ] Provide a simple Projects page, Video list page, and Video detail page that:
    - [ ] Shows project selection and active project.
    - [ ] Lists uploaded videos and their status.
    - [ ] Allows triggering pre-processing and inference.
  - [ ] Copy interaction patterns and bounding-box overlay styles from the `/demo/detection-overlay` reference page (`templates/mock_detection_overlay.html`).

### 1.8 Word Report Export (Minimal)

Implement a basic reporting service in `app/services/reporting_service.py`.

- [ ] **Report data selection**
  - [ ] For Phase 1, allow exporting a report for a **single video** within a project.
  - [ ] Include basic metadata (project, video, timestamp) and a summary of detections.

- [ ] **python-docx integration**
  - [ ] Generate a `.docx` file and save it under a predictable path (e.g., `reports/<project_id>/`).

- [ ] **Endpoint**
  - [ ] `POST /videos/<id>/report` – creates a report and returns a download URL/path.

---

## Phase 2 – Multi-Model & Benchmarking (MVP Extended)

Goal: extend the MVP to support multi-model inference and basic benchmarking/cost metrics.

### 2.1 Multi-Model Inference

- [ ] **Extend InferenceRun model**
  - [ ] Ensure `model_ids` and `params` can represent multiple Clarifai models.

- [ ] **Service logic**
  - [ ] Implement `run_multi_model_inference(frames, model_ids, config)` in `inference_service.py`.
  - [ ] Store per-model results in `InferenceRun.results` and/or a `Detection` table for richer querying.

- [ ] **API**
  - [ ] `POST /videos/<id>/multi-inference` – accept a list of model IDs and parameters.

### 2.2 Benchmarking & Metrics

- [ ] **Metrics service** (`app/services/metrics_service.py`)
  - [ ] Compute per-model averages, hit frequency, detection density, and efficiency ratio.
  - [ ] Implement helper functions that operate over `InferenceRun` and `Detection` data.

- [ ] **Endpoints**
  - [ ] `GET /projects/<id>/benchmark` – return metrics for all models used in the project.
  - [ ] `GET /inference-runs/<id>/metrics` – metrics for a specific run.

### 2.3 Cost Estimation

- [ ] **Billing service** (`billing_service.py`)
  - [ ] Implement `estimate_project_cost(project_id, fps, model_ids, duration)` using a simple pricing model.
  - [ ] Track basic `cost_actual` based on recorded API usage.

- [ ] **UI**
  - [ ] Show projected vs actual cost per model and per project on the dashboard.

### 2.4 UI: Model Comparison View (Basic)

- [ ] Implement:
  - [ ] An Efficiency Matrix (simple table or bar chart) comparing models by confidence and cost.
  - [ ] A basic comparison view for a single frame/time index showing overlays from two models (A/B toggle is sufficient for Phase 2).

---

## Phase 3 – Forensic Depth (Checklist for Later)

- [ ] Implement ROI-based contextual re-inference (user selects region → re-run inference at higher resolution).
- [ ] Add Gemini-powered narrative generation for project-level summaries.
- [ ] Extend the report export to include ROI-derived evidence and narratives.

---

## Phase 4 – Scaling & Telemetry for POC (Checklist for Later)

- [ ] Add more detailed telemetry for inference runs, costs, and performance timings.
- [ ] Optimize DB queries using appropriate indexes, especially around JSONB fields.
- [ ] Improve UI responsiveness and refine the Mission Control dashboard layout.

---

## General Notes for Coding Agent

- Always keep implementations consistent with:
  - `SoftwareSpecification.md`
  - `Technical Implementation Plan.md`
  - `TechnologyStack.md`
  - `UI Coding Guidance.md`
- Reuse the shipped reference assets before writing new scaffolding:
  - `docs/ClarifaiAPI.md` for SDK parameters, auth, and batching examples.
  - `scripts/demo_logo_detection.py` to validate PAT/model settings or capture sample payloads.
  - `.env.example` / `.env` for Clarifai configuration shared between CLI tools and Flask services.
  - `/demo/detection-overlay` (template in `templates/mock_detection_overlay.html`) for bounding-box overlay patterns and payload layout.
- When in doubt, default to **simplicity** and **single-user, local POC** constraints.
- Prefer small, well-named modules and functions that map clearly to these tasks.
