# VideoLogoDetection User Guide

This guide walks through setting up the environment, running the application, and using the dashboard to analyze videos and export run artifacts.

## 1. Prerequisites

- macOS (tested) with Podman or Docker Desktop for the PostgreSQL container.
- Conda (Miniconda/Anaconda) to manage the `VideoDetection-312` environment.
- Clarifai and Gemini API credentials (optional for stubbed inference but required for real detections).

## 2. First-Time Setup

1. **Start PostgreSQL via Podman Compose**
   ```bash
   podman-compose up -d db
   ```
   The container exposes Postgres 15 on `localhost:35432` with credentials defined in `podman-compose.yaml`.

2. **Create and activate the conda env**
   ```bash
   ./setup-conda-env.sh
   ```
   This script creates `VideoDetection-312`, installs dependencies from `requirements.txt`, and ensures system packages (e.g., `pkg-config`) are available.

3. **Load environment variables + schema**
   ```bash
   ./setup-env.sh
   ./setup-database.sh
   ```
   These scripts export database connection variables and apply `create-schema.sql` inside the running Postgres container.

4. **Launch the Flask + Socket.IO server**
   ```bash
   ./start.sh
   ```
   The UI loads at http://127.0.0.1:4000 by default.

## 3. Daily Workflow

### 3.1 Open the Dashboard
- Open the root page (`/`). The app auto-selects the most recent project and displays key cost metrics.
- Switch projects or create a new one from the “Active Project” card.

### 3.2 Manage Videos and Clips
- Use the Preprocessing tab to register videos and define up to five custom clip windows per asset.
- Status updates stream live via Socket.IO (`preprocess_status`). Once clips are ready, the video becomes available on the dashboard.

### 3.3 Run Inference
1. In **Frame Overlay Review**, choose:
   - Clip (or entire video if no clips exist)
   - Run (the dropdown lists latest completed runs)
   - Two models to compare (Model A/B)
   - Sampling parameters: FPS, min confidence, max concepts, batch size
2. Click **Run Inference**. Progress and cost estimates update in real time. When the run finishes, detections populate the overlay and detection list.

### 3.4 Review Detections
- Use the zoom controls on the overlay to inspect bounding boxes.
- Toggle between Model A and Model B to compare hits and false positives.
- The detection list mirrors the currently visible frame.

### 3.5 Export a Run
1. Ensure the run selector next to Frame Overlay Review points to the run you want.
2. Click **Export Run**.
3. The app streams `run_<id>.zip` to your browser with the structure:
   - `frames/` – PNG overlays (Model A = red `#FF0000`, Model B = dark blue `#003366`).
   - `json/` – per-model per-frame JSON plus optional `detections_aggregate.json`.
   - `manifest.json` – metadata (project, video, timestamps, file counts, optional checksums).
4. The same archive is saved to `reports/run_<id>.zip` on disk for later sharing.

### 3.6 Generate Word Reports
- From the video card menu, choose **Generate Report**. The backend builds a `.docx` document with project metadata, per-model tables, and detection summaries. Files land under `reports/project_<project_id>/`.

## 4. Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `which podman` shows two paths | Remove `/opt/podman/bin` from `PATH` or set `podman.binary.path` in VS Code settings so only `/opt/homebrew/bin/podman` is used. |
| Conda env not auto-activating in VS Code terminal | Verify `.vscode/settings.json` sets `terminal.integrated.defaultProfile.osx` to `zsh-conda`. New terminals should show `CONDA_DEFAULT_ENV=VideoDetection-312`. |
| Export button disabled | Ensure a run is selected in the dropdown; the button auto-enables when `state.comparison.runId` is populated. |
| `python` command missing | Use `python3` inside macOS shells or rely on the `VideoDetection-312` conda env where `python` points to 3.12. |

## 5. Reference Scripts

- `scripts/run_local_inference.py` – smoke-test Clarifai integration end-to-end.
- `scripts/test_overlay_helper.py` – verifies overlay helper renders Model A/B colors correctly.
- `scripts/load_sample_data.py` – seeds demo projects/videos.

## 6. Support Artifacts

- **REPORT.md** – detailed export specification with schema examples.
- **REPORT-Tasks.md** – actionable checklist for agents implementing or verifying the export flow.
- **SoftwareSpecification.md** – complete requirements reference.

Follow this guide each time you onboard a new analyst or need to reproduce the workflow on a fresh machine.
