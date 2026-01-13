# Run Export Specification (Example: Run #43)

This document specifies the export format and example content for a single inference run. The example below references Run #43.

## Overview
- Purpose: Provide a portable report containing both visual and machine-readable outputs.
- Contents:
  - Frame image(s) with bounding boxes overlaid.
  - JSON outputs for detections from both Model A and Model B.

## Output Layout
- Root folder: `reports/run_43/`
- Subfolders:
  - `frames/`: PNG images with bounding boxes drawn.
  - `json/`: JSON outputs for detections.
- Recommended files:
  - `reports/run_43/frames/frame_000043_overlay.png`
  - `reports/run_43/json/model_A_frame_000043.json`
  - `reports/run_43/json/model_B_frame_000043.json`
  - Optional aggregate: `reports/run_43/json/detections_aggregate.json`

## Image Overlay Requirements
- Format: PNG (`*_overlay.png`).
- Coordinate system: origin at top-left; `x` increases to the right, `y` increases downward.
- Bounding box fields: `x`, `y`, `width`, `height` in pixel units of the source frame.
- Visual style:
  - Model A: red boxes (hex `#FF0000`), 2px stroke, label + confidence text.
  - Model B: dark blue boxes (hex `#003366`), 2px stroke, label + confidence text.
- Text format: `LABEL (confidence%)` placed above the box, with semi-transparent background for readability.

## JSON Schema Requirements
Two options are supported: per-model, per-frame JSON files, and an aggregate JSON file.

### Per-Model, Per-Frame JSON
- Path: `reports/run_43/json/model_<A|B>_frame_<FRAME_ID>.json`
- Schema:
```json
{
  "runId": 43,
  "frameId": 43,
  "timestampMs": 1234,
  "source": {
    "projectId": "project_1",
    "videoId": "video_1"
  },
  "model": "A",
  "detections": [
    {
      "label": "BrandX",
      "confidence": 0.94,
      "bbox": { "x": 120, "y": 80, "width": 200, "height": 90 },
      "score": 0.94,
      "classId": "brandx",
      "frameIndex": 43
    }
  ],
  "diagnostics": {
    "inferenceTimeMs": 37,
    "version": "v1.0"
  }
}
```
- Notes:
  - `confidence`/`score` are interchangeable if the model already provides one.
  - Add any model-specific metadata under `diagnostics`.

### Aggregate JSON (Optional)
- Path: `reports/run_43/json/detections_aggregate.json`
- Schema:
```json
{
  "runId": 43,
  "frames": [
    {
      "frameId": 43,
      "timestampMs": 1234,
      "detections": [
        {
          "model": "A",
          "label": "BrandX",
          "confidence": 0.94,
          "bbox": { "x": 120, "y": 80, "width": 200, "height": 90 }
        },
        {
          "model": "B",
          "label": "BrandX",
          "confidence": 0.91,
          "bbox": { "x": 118, "y": 82, "width": 202, "height": 92 }
        }
      ]
    }
  ]
}
```

## File Naming Conventions
- Run folder: `run_<RUN_ID>` (e.g., `run_43`).
- Frames: `frame_<FRAME_ID>_overlay.png` with zero-padded frame indices recommended (e.g., `frame_000043_overlay.png`).
- JSON:
  - Per-model: `model_A_frame_<FRAME_ID>.json`, `model_B_frame_<FRAME_ID>.json`.
  - Aggregate: `detections_aggregate.json`.

## Example Report Content (Run #43)

### Visual Output
Embed the overlaid frame image in Markdown:

![Run 43 — Frame 000043 Overlay](reports/run_43/frames/frame_000043_overlay.png)

### Model A — JSON Output (Frame 000043)
```json
{
  "runId": 43,
  "frameId": 43,
  "timestampMs": 1234,
  "model": "A",
  "detections": [
    {
      "label": "BrandX",
      "confidence": 0.94,
      "bbox": { "x": 120, "y": 80, "width": 200, "height": 90 }
    }
  ]
}
```

### Model B — JSON Output (Frame 000043)
```json
{
  "runId": 43,
  "frameId": 43,
  "timestampMs": 1234,
  "model": "B",
  "detections": [
    {
      "label": "BrandX",
      "confidence": 0.91,
      "bbox": { "x": 118, "y": 82, "width": 202, "height": 92 }
    }
  ]
}
```

## Generation Notes (Optional)
- Use existing inference outputs and draw overlays via the reporting utilities.
- Store assets under `reports/run_43/` for portability and archiving.
- Ensure consistent coordinate system and units across models to allow side-by-side comparison.

## Validation Checklist
- Image shows all detections from both models with proper color coding.
- JSON files present with correct schema and non-empty `detections` arrays.
- Paths resolve within the repository (or export package) and can be opened without additional tooling.

## Zip Packaging & UI Download

### Archive Output
- Purpose: Produce a single downloadable artifact containing `frames/` and `json/`.
- Archive name: `reports/run_43.zip`.
- Archive contents (root of the zip):
  - `run_43/frames/` with overlaid PNGs (e.g., `frame_000043_overlay.png`).
  - `run_43/json/` with per-model and aggregate JSON (optional).
  - `run_43/manifest.json` summarizing contents (recommended).

### `manifest.json` (Recommended)
Placed at `run_43/manifest.json` inside the archive.
Example schema:
```json
{
  "runId": 43,
  "projectId": "project_1",
  "videoId": "video_1",
  "createdAt": "2026-01-13T10:00:00Z",
  "items": {
    "frames": ["frame_000043_overlay.png"],
    "json": [
      "model_A_frame_000043.json",
      "model_B_frame_000043.json",
      "detections_aggregate.json"
    ]
  },
  "counts": { "frames": 1, "json": 3 },
  "toolVersion": "report-spec v1"
}
```

### Download API (UI Integration)
- Endpoint: `GET /api/reports/run/43/download`
- Response:
  - `Content-Type: application/zip`
  - `Content-Disposition: attachment; filename=run_43.zip`
  - Body: zip stream of `reports/run_43.zip` (generated on-demand or prebuilt).
- Status codes:
  - `200` — Download stream starts.
  - `202` — Archive is being prepared; client should poll until ready.
  - `404` — Run not found.
  - `500` — Packaging failed.

### UI Behavior
- Add an “Export” button for the selected run.
- On click: call `GET /api/reports/run/<runId>/download`.
- If `202`, show progress indicator and retry until `200`.
- On `200`, trigger browser download.

### Packaging Implementation Notes
- Preferred approach: stream zip generation to avoid large temp files for multi-frame runs.
- Safe name normalization for all included files to avoid path traversal.
- Optional: include checksums (`sha256`) in `manifest.json` for integrity validation.
- Optional: server-side caching to reuse previously generated archives.
