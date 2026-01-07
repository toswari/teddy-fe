Technical Implementation Plan – VideoLogoDetection

This document translates the VideoLogoDetection Software Specification into a concrete, phased implementation plan. It assumes the stack defined in SoftwareSpecification.md (Python 3.11, Flask, PostgreSQL/JSONB, Clarifai, Gemini, PyAV, OpenCV, python-docx), with long-running work initially executed in-process (no Redis or external task broker).

---

Phase 1: Core Infrastructure & Scaffolding (Spec: Sections 1, 3, 4)

1. Containerization & Environment
- Create a Dockerfile for the Flask backend.
- Create podman-compose.yaml with the following service:
	- db: PostgreSQL with persistent volume and JSONB enabled (default in Postgres 9.4+), exposed on a non-standard host port as defined in the spec.
- Mount a /media volume (host directory) for source videos and generated clips, if needed.
- Wire environment variables for DATABASE_URL, CLARIFAI_PAT, and Gemini API key (no Redis or Celery-related env vars).

2. Flask Application Factory & Extensions
- Implement create_app() in app/__init__.py using the Application Factory Pattern.
- Initialize the following extensions inside the factory:
	- SQLAlchemy (PostgreSQL/JSONB models).
	- Flask-SocketIO (for real-time progress events).
- Register blueprints for:
	- api.projects
	- api.videos
	- api.inference
	- api.reporting
	- api.metrics (for cost/usage telemetry)

3. Base Directory Structure (Spec-aligned)
- app/
	- __init__.py (create_app, init_extensions)
	- models/ (SQLAlchemy models)
	- services/ (AI, video, billing, reporting, telemetry)
	- api/ (Blueprints for REST + SocketIO namespaces)
	- tasks/ (optional background/job helpers; MVP may call services synchronously without an external broker)
	- config.py (environment-specific configuration)

---

Phase 2: Data Modeling & Validation (Spec: Sections 2.1, 2.4, 2.5, 7)

1. SQLAlchemy Models (PostgreSQL + JSONB)
- Project
	- id, name, description
	- settings JSONB (FPS, active Clarifai models, thresholds)
	- budget fields (budget_limit, currency)
	- last_opened_at (timestamp for "continue where I left off" behavior)
- Video
	- id, project_id (FK)
	- original_path, storage_path, duration_seconds, resolution
	- status (uploaded, processed, failed)
- InferenceRun
	- id, project_id, video_id
	- model_ids (array or JSONB)
	- params JSONB (FPS, sampling strategy, ROI settings)
	- results JSONB (Clarifai/Gemini responses, detections, bounding boxes)
	- cost_actual, cost_projected, efficiency_ratio
	- status (pending, running, completed, failed)
- Detection (optional table for heavy analytics)
	- id, inference_run_id
	- frame_index, timestamp_seconds
	- model_id, label, confidence
	- bbox JSONB (x, y, w, h)

2. Validation & Schemas
- Use Marshmallow schemas for incoming REST payloads:
	- ProjectCreateSchema (name, description, initial settings)
	- ProjectUpdateSchema (name, description, settings)
	- VideoUploadSchema
	- InferenceRequestSchema (FPS, model IDs, ROI, pricing options)
- Use Pydantic models for internal service layer contracts (e.g., VideoProcessingConfig, ClarifaiRequestPayload) to ensure strong typing and easier refactoring.

---

Phase 3: Video Pre-processing & Clipping (Spec: Section 2.2)

1. Stream Copy & Clipping Engine
- Implement video_service.py in app/services/ with functions:
	- probe_video_metadata(path) using ffmpeg-python or PyAV.
	- generate_clips(source_path, clip_length=20s) using FFmpeg -c copy.
- Ensure operations write to the /media volume and update Video records.

2. Frame Sampling & Normalization
- Use PyAV (av) for keyframe-accurate seeking and frame extraction.
- Implement motion-based sampling:
	- Compute pixel deltas between frames.
	- Only keep frames where change > 2% threshold (spec requirement).
- Use OpenCV (cv2) to normalize contrast/brightness for sampled frames.

3. Background Execution (Optional, In-Process)
- For the MVP, call pre-processing and frame extraction services synchronously from the API layer.
- If later needed, introduce a simple in-process background execution mechanism (e.g., Python threads or a lightweight task queue) that does not depend on Redis or an external broker.
- Ensure any background execution mechanism can still emit progress events through SocketIO for real-time UI feedback.

---

Phase 4: AI Inference & Benchmarking (Spec: Sections 2.2, 2.3, 2.4)

1. Clarifai Multi-Model Inference
- Implement clarifai_service.py in app/services/:
	- build_clarifai_client(CLARIFAI_PAT)
	- run_multi_model_inference(frames, model_ids, config)
- Send frames in batches for efficiency.
- Persist raw responses and normalized detection structures into JSONB (InferenceRun.results and Detection rows).

2. Contextual Re-Inference (Forensic Depth)
- Implement ROI-based re-scan endpoints and tasks:
	- POST /inference/{run_id}/roi re-queues selected ROIs for higher-resolution inference.
	- Store ROI-specific results and link them to the parent InferenceRun.
- Integrate optional Gemini calls for narrative/summary generation per project.

3. Benchmarking & Metrics
- Implement metrics_service.py to compute:
	- Average confidence by model.
	- Hit frequency and detection density over timeline.
	- Cost per valid detection (Efficiency Ratio) as defined in the spec.
- Expose metrics via /metrics and /projects/{id}/benchmark endpoints.

---

Phase 5: Pricing, Cost Tracking & Reporting (Spec: Sections 2.4, 2.5, 6)

1. Cost Estimation Engine
- Implement billing_service.py:
	- estimate_project_cost(project_id, fps, model_ids, duration)
	- track_actual_cost(inference_run_id, api_usage)
- Use Clarifai and Gemini pricing inputs to compute projections and actuals.

2. Real-time Analytics & Guardrails
- Store per-call usage in a BillingEvent table or JSONB logs.
- Compute running totals per project and expose via SocketIO and REST.
- Implement budget guardrails:
	- Hard cap (reject new inference runs over budget).
	- Soft warnings (UI notifications at 50%, 80%, 100% of budget).

3. Forensic Reporting
- Implement reporting_service.py using python-docx:
	- generate_report(project_id, selected_detections)
- Include:
	- Key frames with bounding boxes.
	- Per-model statistics and efficiency table.
	- Optional benchmarking summary matching the spec’s "Model Efficiency" section.

---

Phase 6: UX, Mission Control & Real-time Dashboard (Spec: Section 5)

1. Mission Control API & Socket Channels
- Design endpoints and SocketIO namespaces for:
	- /projects, /videos, /inference, /reports
	- Channels: progress, cost_updates, detection_stream

2. Project List & "Continue" Behavior
- Implement REST endpoints in api.projects:
	- GET /projects – list all projects with summary info (video count, last activity).
	- GET /projects/recent – return the most recently opened project (based on last_opened_at).
	- PATCH /projects/{id} – update project metadata and settings.
- Ensure the UI always scopes videos, inference runs, and reports to the currently selected project.
- When a project is opened from the UI, update last_opened_at so "continue last project" can show the right entry.

3. Smart Timeline & Comparison Views
- Provide backend data for:
	- Timeline heatmap (aggregated detections per time bucket).
	- A/B comparison: per-frame detections grouped by model.
- Ensure APIs support fetching detections by frame/time window and model.

---

Phase 7: Scaling, Telemetry & Hardening (Spec: Sections 6, 7)

1. Performance Optimization
- Optimize query patterns for InferenceRun and Detection using JSONB indexes.
- Add background aggregation jobs for benchmarking queries over 1M+ detections.

2. Telemetry & Logging
- Standardize Loguru logging across services.
- Add structured logs for:
	- Inference runs
	- Billing events

3. Deployment Considerations
- Validate performance targets from the spec:
	- 20s clip generation < 2.0s under typical conditions.
	- Benchmarking query < 1.0s for 1M+ detections with proper indexes.
	- Cost accuracy within 5% of actual billing (validate via shadow billing reports).

This plan is intentionally implementation-focused while staying traceable back to SoftwareSpecification.md, ensuring each feature, metric, and performance target has a concrete technical path.