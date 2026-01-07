# VideoLogoDetection Software Specification – Snapshot v2.2.0

## 1. Project Overview

This document is the primary technical reference for the VideoLogoDetection application. It merges:

- The initial Software Requirements Specification (SRS)
- The agreed technology stack
- Key architectural and coding guidelines

The goal is to guide a small implementation team to deliver a focused, single-user proof-of-concept (POC) while keeping a clear path to future hardening and extension.

### 1.1 MVP Definition

The Minimum Viable Product (MVP) is a functional forensic tool capable of:

- **Video Segmentation**  
	Pre-processing long-form videos (up to 2 hours) into digestible 20-second clips.

- **Visual Inference**  
	Executing frame-by-frame AI analysis using one or more Clarifai models simultaneously.

- **Active Visualization**  
	Running video playback with dynamic bounding box overlays, confidence level indicators, and model-specific labels.

- **Cost Management**  
	Estimating analysis costs before execution based on video length, sampling parameters, and active models.

- **Forensic Reporting**  
	Exporting curated frames and metadata into a formatted `.docx` report suitable for human review.

- **Model Benchmarking**  
	Comparing the performance (accuracy/confidence) and cost-efficiency of different models within the same project.

- **Project Management**  
	Managing multiple projects (cases) in parallel, each with its own configuration, videos, inference runs, and reports, and allowing the analyst to quickly resume work on a recently used project.

### 1.2 Assumptions & Scope

- **Single-User POC**  
	Maximum of one concurrent user (single analyst) is assumed. No multi-tenant or large-team collaboration requirements.

- **POC Only**  
	This specification targets a proof-of-concept deployment, not a hardened production system. Operational concerns (HA, auto-scaling, full observability) are minimized.

- **Security & Access**  
	The application is assumed to run on a trusted, local environment for a single user. No authentication flows, MFA, SSO, RBAC, or compliance-oriented security work are required for this phase.

- **Environment**  
	- Containerized deployment via Docker/Podman Compose on a single host.  
	- No requirement for GPU; implementation should be CPU-first but not preclude future GPU offload.

---

## 2. Functional Requirements

### 2.1 Core Features

- **Real-time Dashboard**  
	Live telemetry of processing state and cost estimates with perceived latency under 500 ms for UI updates.

- **Refined Logic for Multi-Video Forensics**  
	Support for project-based workflows where multiple videos are analyzed, compared, and reported on within a single logical “case”.

### 2.2 Video Pre-processing & Clipping

- **Long-Form Support**  
	- Must support input videos up to 2 hours in duration.  
	- Target resolutions: at least 1080p support; behavior on higher resolutions (4K) should degrade gracefully.

- **Visual Normalization**  
	Automated adjustment of exposure/contrast to improve AI consistency across clips and frames.

- **Motion-Based Sampling**  
	- Use pixel-delta thresholds (> 2% change) to decide whether a frame is “interesting” enough to analyze.  
	- Goal: reduce API calls and cost while preserving important events.

- **Configurable Sampling Rate (FPS)**  
	- User can set FPS for inference (e.g., 1 FPS, 5 FPS).  
	- Effective frame selection can be a combination of fixed FPS and motion-based filtering.

- **Multi-Model Inference Orchestration**  
	Allow the user to select multiple Clarifai models and run them concurrently over the same set of frames.

- **Automated Forensic Clipping**  
	Generate 20-second video segments around relevant events using FFmpeg `-c copy` to avoid re-encoding when possible.

### 2.3 Contextual Re-Inference (Forensic Depth)

- **High-Stakes ROI (Region of Interest)**  
	- Allow manual selection/cropping of specific frame areas.  
	- Re-run Clarifai (or Gemini for reasoning) on the higher-resolution region to increase confidence for critical frames.

### 2.4 Model Performance & Cost Benchmarking

The system must generate a comparison matrix for projects using multiple models.

- **Performance Metrics**  
	- Average confidence score per model.  
	- Frequency of “Hit” detections per model.  
	- Detection density over the video timeline.

- **Cost Metrics**  
	- Actual API cost per model.  
	- “Cost per Valid Detection” (Efficiency Ratio):  
		- A valid detection is any detection above a configurable confidence threshold and not explicitly dismissed by the user.  
		- Efficiency Ratio = `total_cost_for_model / number_of_valid_detections`.

- **A/B Visualization**  
	- Side-by-side or toggleable video playback.  
	- For any given frame, show Model A vs Model B overlays to help identify:  
		- False positives (over-detection)  
		- Missed detections (under-detection)

### 2.5 Pricing Estimation & Token Tracking

- **Cost Calculator**  
	- Pre-analysis cost projection based on:  
		- Video length  
		- FPS and motion-based sampling configuration  
		- Number and type of active Clarifai models  
	- Must display projected cost per model and projected total.

- **Real-time Analytics**  
	- Track actual API usage and costs per project.  
	- Provide basic budget guardrails:  
		- Simple thresholds that warn when the projected or actual spend exceeds configured soft/hard limits.

---

## 3. Technology Stack & Rationale

### 3.1 Backend & Infrastructure

- **Python 3.11 / Flask 2.3.3**  
	- Provides a lightweight, flexible web framework.  
	- Uses the Application Factory Pattern and Blueprints to keep the code modular and testable.

- **PostgreSQL (JSONB)**  
	- Primary data store using SQLAlchemy ORM.  
	- JSONB fields are used to store heterogeneous model responses and detection metadata in a queryable form.

- **Background Execution (In-Process Only for POC)**  
	- Long-running work (video pre-processing, frame sampling, inference orchestration) is executed in-process within the Flask application for the MVP.  
	- If any background-style execution is introduced, it must rely only on lightweight, brokerless mechanisms (e.g., Python threads or in-process queues) and must not introduce Redis, Celery, or other external task brokers.

### 3.2 Computer Vision & AI

- **Clarifai Platform**  
	- Primary object-of-interest (OOI) detection engine.  
	- Supports calling multiple model IDs in parallel for benchmarking.

- **Google Gemini API**  
	- Used selectively for multimodal reasoning and narrative generation in forensic reports or summaries.

- **PyAV (av)**  
	- Provides keyframe-accurate seeking and frame extraction for precise sub-clipping and sampling.

- **OpenCV**  
	- Used for visual normalization and optional image pre-processing steps.

---

## 4. Modular Architecture & Directory Structure

The application follows the **Application Factory Pattern** and a **Service Layer Pattern** to promote separation of concerns and maintainability.

### 4.1 High-Level Modules

- **API Layer (Flask Blueprints)**  
	- HTTP endpoints and WebSocket/SocketIO events.  
	- Thin controllers: validation, orchestration, and delegation to services.

- **Service Layer**  
	- Encapsulates business logic for:  
		- Video ingestion and pre-processing.  
		- AI inference orchestration (Clarifai / Gemini).  
		- Cost estimation and billing metrics.  
		- Reporting (Word export, benchmarking tables).

- **Execution Layer (In-Process Jobs)**  
	- For the POC, long-running jobs (video clipping, frame extraction, batch inference, ROI re-inference, aggregation) run in-process, either synchronously or via lightweight, brokerless helpers (e.g., threads or in-process queues).  
	- No Redis, Celery, or external worker infrastructure is introduced in the MVP.

- **Data Access Layer (SQLAlchemy Models)**  
	- Defines core entities:  
		- Project, Video, InferenceRun, Detection, and billing/usage records.

### 4.2 Recommended Directory Structure

Back-end code SHOULD follow a consistent, modular layout:

- app/__init__.py – application factory and extension setup  
- app/config.py – environment-specific configuration  
- app/models/ – SQLAlchemy models (Project, Video, InferenceRun, Detection, etc.)  
- app/services/ – video, inference (Clarifai/Gemini), billing, reporting, metrics  
- app/api/ – Flask blueprints and request/response schemas  
- app/tasks/ – optional in-process job helpers (no external brokers)  
- tests/ – unit and integration tests mirroring the app/ structure  

---

## 5. User Experience & Design



- **Visibility of System Status**  
	- Clearly display job progress, queue status, and cost projection/actuals.

- **User Control & Agency**  
	- Allow users to enable/disable specific models, adjust FPS and thresholds, and select/deselect detections for reporting.

- **Efficiency**  
	- Provide smart markers, heatmaps, and comparison views to reduce the time needed to reach a forensic conclusion.

### 5.2 The Forensic User Journey

- **Phase 1–2: Onboarding & Analysis**  
	- Upload or select videos for a project.  
	- Configure FPS, models, and cost guardrails.  
	- Trigger analysis and monitor progress through the dashboard.

- **Phase 3: Model Comparison View**  
	- View the Efficiency Matrix: a bar/summary chart of “Cost vs. Confidence” for each model used in the project.  
	- Use the Comparison Player to toggle or split-screen model overlays for the same frames.

- **Phase 4: Review & Curation**  
	- Use a unified collection tray where detections from any model can be “snapped” for inclusion in the report.  
	- The originating model is automatically tracked in metadata.

- **Phase 5: Finalization & Export**  
	- Generate a `.docx` report that includes:  
		- Key frames with bounding boxes and metadata.  
		- A model efficiency table and cost metrics.  
		- Optional narrative summaries (via Gemini).

---

## 6. Implementation Roadmap (High-Level)

- **Phase 1 (MVP Core)**  
	- Modular foundation, basic data model.  
	- FFmpeg clipping, Clarifai single-model inference.  
	- Basic dashboard and Word export.

- **Phase 2 (Multi-Model & Benchmarking)**  
	- Parallel Clarifai model execution.  
	- Comparison Dashboard UI (Efficiency Matrix, split-screen/toggle).  
	- Core cost-per-detection logic.

- **Phase 3 (Forensic Depth)**  
	- ROI-based contextual re-inference.  
	- Optional Gemini-powered reasoning and narratives.

- **Phase 4 (Scaling & Telemetry for POC)**  
	- More advanced telemetry and UX polish within the single-user constraint.  
	- Performance tuning to hit the defined targets.

---

## 7. Performance Targets

- **Clipping Latency**  
	- A 20-second clip from a 2-hour source should be produced in under 2.0 seconds under typical conditions.

- **Benchmarking Query Latency**  
	- Retrieval of benchmarking data for 1M+ detections in under 1.0 second with proper indexing and aggregation.

- **Cost Accuracy**  
	- Projected cost should be within 5% of actual API billing based on known pricing inputs for Clarifai and Gemini.

---

## 8. Coding Guidelines

### 8.1 Modularity & Separation of Concerns

- Follow the Application Factory Pattern: configuration, app creation, and extension initialization live in dedicated modules.
- Keep route handlers thin; move business rules and workflow logic into services.
- Prefer composition over inheritance; use small, focused functions and classes.
- Avoid cross-coupling between unrelated modules; introduce clear interfaces where boundaries cross.

### 8.2 Directory & File Structure

- Maintain the structure described in section 4.2.  
- Mirror `app/` structure under `tests/` for easier test discovery and maintenance.
- Avoid circular imports by:  
	- Grouping domain models together.  
	- Placing shared utilities (constants, helpers) into dedicated modules.

### 8.3 Testing Practices

- **Unit Tests**  
	- Focus on:  
		- Video sampling logic (FPS + motion-based filtering).  
		- Cost estimation and efficiency ratio calculations.  
		- Metrics aggregation for benchmarking.

- **Integration Tests**  
	- Cover end-to-end flows:  
		- Project creation, video registration.  
		- Triggering an inference run and verifying persisted results.  
		- Generating a basic report.

- **Test Isolation**  
	- Use containerized dependencies or mocks for Postgres, Clarifai, and Gemini.  
	- Ensure tests are deterministic with fixed test vectors (test videos, canned API responses).

- For this POC, prioritize tests around the core forensic and cost-tracking flows over exhaustive coverage of UI details.

### 8.4 Code Quality & Style

- Follow PEP 8 for Python style and use type hints for public service interfaces and models where beneficial.
- Use structured logging (e.g., with Loguru) for:  
	- Inference runs  
	- Billing calculations  
	- Error conditions
- Document non-obvious design decisions in:  
	- Short docstrings for complex functions, and/or  
	- The Technical Implementation Plan for higher-level decisions.

---

## 9. Traceability

Each major functional area in this specification should have a corresponding section or phase in:

- **Technical Implementation Plan** – for concrete phases, tasks, and module breakdown.
- **Test Plan (future)** – for mapping requirements to concrete test cases.

Implementation work SHOULD always reference the requirement IDs and sections in this document to ensure traceability from spec → implementation → validation.
