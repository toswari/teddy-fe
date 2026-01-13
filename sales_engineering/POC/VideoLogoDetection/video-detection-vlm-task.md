# Video Detection VLM — UI Integration Task List

This task list guides adding two LM Studio VLMs into the application UI using the workflow documented in `video-detection-vlm.md`.

## Scope
- Integrate `qwen/qwen2.5-vl-7b` and `zai-org/glm-4.6v-flash` as selectable Vision-Language Models (VLMs) in the dashboard.
- Enable running VLM inference on existing runs’ frames and display Model B overlays.

## Tasks

- [x] Add API: `/api/vlm/models` — proxy LM Studio `GET /v1/models` and return `{count, models: [{id, ...}]}`
  - Input: none (optional `q`, `per_page` for future filtering)
  - Output: JSON list of model IDs; ensure IDs match LM Studio exactly
  - Config: read `LMSTUDIO_BASE_URL` (default `http://localhost:1234/v1`)

- [x] Add UI: VLM section in `dashboard-inference.html`
  - Dropdown: `id="vlm-model-select"` populated by `/api/vlm/models`
  - Pinned options at top: `qwen/qwen2.5-vl-7b`, `zai-org/glm-4.6v-flash`
  - Controls: `--limit` numeric input (default 3), Run button `id="vlm-run-btn"`
  - Status line: show selected run, frames processed, and detections count

- [x] Backend trigger: `/api/vlm/run`
  - Inputs (JSON body): `{ runId: number, modelId: string, limit?: number }`
  - Behavior: invoke existing VLM logic (refactor from `scripts/test-vlm-app.py` into a service) to process frames and write
    - JSON: `reports/run_<id>/json/model_B_frame_<frame>.json`
    - Overlays: `reports/run_<id>/frames/frame_<frame>_overlay.png`
  - Response: `{ processed: number, frames: [idx...], outputsDir: "reports/run_<id>" }`

- [x] Overlay integration in UI
  - Add toggle to comparison panel: `id="comparison-model-vlm"` representing Model B overlays
  - Load `frame_<idx>_overlay.png` from reports and display them in the overlay canvas
  - Update detection list with VLM entries when Model B is active

- [x] Configuration
  - Expose `LMSTUDIO_BASE_URL` in server config and `.env` script; default to `http://localhost:1234/v1`
  - Document `LMSTUDIO_MODEL_ID` environment override for CLI/testing

- [x] Update documentation
  - In `video-detection-vlm.md`, add “UI Integration Targets” listing:
    - `qwen/qwen2.5-vl-7b` (Qwen2.5-VL 7B)
    - `zai-org/glm-4.6v-flash` (GLM 4.6v Flash)
  - Note parser resilience to `<think>` preambles and mixed bbox formats

- [x] Tests
  - Unit: API `/api/vlm/models` mock LM Studio response
  - Integration: run `/api/vlm/run` in test mode limiting to 1 frame; assert JSON/overlay files exist
  - UI: smoke test populating dropdown and triggering a fake run

## Acceptance Criteria
- VLM dropdown appears and lists LM Studio models with pinned entries for Qwen2.5-VL 7B and GLM 4.6v Flash.
- Clicking “Run VLM” processes frames for the selected run, writes Model B JSON/overlays, and updates the overlay view.
- Parser handles `<think>` preambles and both normalized and pixel bbox formats (as per `video-detection-vlm.md`).
- Configuration and docs are clear; default local LM Studio works without extra setup.

## Notes
- Reuse normalization and parsing logic from `scripts/test-vlm-app.py` to avoid duplication; consider moving it into `app/services/inference_service.py`.
- Keep long-running work synchronous for now (small limits) to match POC constraints; future iteration can introduce a background queue.
