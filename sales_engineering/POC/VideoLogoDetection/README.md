# VideoLogoDetection POC

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

3. Start the application (command may vary based on implementation):
	```bash
	./start.sh
	```

For detailed requirements and design, see:

- Software specification: SoftwareSpecification.md
- Technical implementation plan: Technical Implementation Plan.md
- Technology stack details: TechnologyStack.md
- UI coding guidance: UI Coding Guidance.md
- API examples: docs/api-examples.md
- Media storage layout: docs/storage-layout.md
- Sample data loader: scripts/load_sample_data.py
- Detection overlay mock: visit `/demo/detection-overlay` in the running app to see a reference UI for drawing bounding boxes and concept badges on top of a frame.

## Running Tests

Install dev deps (pytest) and run:

```bash
pytest
```

The fixtures boot the app in test mode with an in-memory SQLite DB so agents can quickly validate services and APIs before wiring additional features.

## Reference UI Mock

- Start the Flask server (`./start.sh`) and open `http://localhost:5000/demo/detection-overlay` to preview the static detection overlay example.
- The page renders Clarifai-style bounding boxes using Tailwind utility classes so future UI work can copy the structure when implementing the real video detail view.
