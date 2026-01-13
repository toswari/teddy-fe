# Report Export Tasks Checklist (Run #43 example)

Use this checklist to generate and package the export for a single inference run (example: Run 43). Each item is designed for the coding agent to execute end-to-end.

## Preparation
- [x] Confirm run context: project, video, `runId=43`, target frame(s) (e.g., `frameId=43`).
- [x] Create output directories: `reports/run_43/frames/` and `reports/run_43/json/`.

## Overlay Generation
- [x] Ensure color mapping for models:
  - Model A → red `#FF0000`
  - Model B → dark blue `#003366`
- [x] Use `draw_frame_overlay()` to render bounding boxes and labels on the selected frame(s).
- [x] Save image as `reports/run_43/frames/frame_000043_overlay.png` (PNG, 2px strokes).

## JSON Outputs
- [x] Generate per-model, per-frame JSON files under `reports/run_43/json/`:
  - [x] `model_A_frame_000043.json`
  - [x] `model_B_frame_000043.json`
- [x] JSON schema fields (per file): `runId`, `frameId`, `timestampMs`, `model`, `detections[]` (`label`, `confidence`, `bbox {x,y,width,height}` or normalized `{left,top,right,bottom}`), optional `diagnostics`.
- [x] Optional: produce `reports/run_43/json/detections_aggregate.json` combining A+B.

## Manifest
- [x] Create `reports/run_43/manifest.json` with:
  - `runId`, `projectId`, `videoId`, `createdAt`
  - `items.frames[]`, `items.json[]`, `counts.frames`, `counts.json`
  - Optional: per-file `sha256` checksums for integrity.

## Packaging
- [x] Zip the folder as `reports/run_43.zip` with the following structure at the archive root:
  - `run_43/frames/`
  - `run_43/json/`
  - `run_43/manifest.json`
- [x] Prefer streaming zip creation for large runs; avoid large temp files.

## API / Backend Integration
- [x] Implement download endpoint: `GET /api/reports/run/<runId>/download`.
  - Response headers: `Content-Type: application/zip`, `Content-Disposition: attachment; filename=run_<runId>.zip`.
  - Status codes: `200` (stream), `202` (preparing; client should poll), `404` (not found), `500` (failed).
- [x] Use safe name normalization to prevent path traversal.
- [x] Cache generated archives when feasible to reduce repeated work.

## UI Integration
- [x] Add an “Export” button for the selected run (e.g., on dashboard inference view).
- [x] On click: call `GET /api/reports/run/<runId>/download`.
- [x] If `202`, show progress and poll; on `200`, trigger browser download.
- [x] Display simple success/error toast for user feedback.

## Testing & Validation
- [x] Run the overlay helper test: `scripts/test_overlay_helper.py` (generates `frame_000043_overlay.png`).
- [x] Add unit/integration tests:
  - [x] Validate JSON schema keys and non-empty `detections` arrays.
  - [x] Validate that the zip contains expected files and paths.
  - [x] Validate API route returns `200` with `application/zip` and streams content.
- [x] Manual check: open the overlay PNG and verify Model A red / Model B dark blue boxes and label text.

## Documentation
- [x] Ensure [REPORT.md](REPORT.md) reflects the produced artifacts (image paths, JSON examples, zip details, API contract, UI flow).
- [x] Link the report folder paths and any relevant usage instructions.

## Environment & Tooling
- [x] Confirm VS Code integrated terminal uses `zsh-conda` and auto-activates `VideoDetection-312`.
- [x] If `conda` not on PATH, source `/Volumes/DataExt/anaconda3/etc/profile.d/conda.sh` before activation.

## Acceptance Criteria
- [x] Overlay image(s) present with correct colors and readable labels.
- [x] Per-model JSON files exist, follow schema, and contain detections.
- [x] Optional aggregate JSON present if requested.
- [x] `manifest.json` summarizes contents accurately (counts, names, timestamps).
- [x] `reports/run_43.zip` downloads via the API route and unpacks to expected structure.
- [x] UI button triggers export and handles preparation state reliably.
