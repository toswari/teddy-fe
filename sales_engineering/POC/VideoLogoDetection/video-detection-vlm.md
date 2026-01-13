# Video Logo Detection via VLM (LM Studio OpenAI-Compatible API)

This specification defines how to detect logos from video frames using a Vision-Language Model (VLM) served locally through LM Studio’s OpenAI-compatible endpoint.

## Overview
- Goal: Identify logos in frames and return structured detections with bounding boxes.
- Runtime: Local LM Studio at `http://localhost:1234` (OpenAI-compatible)
- Output: Overlaid PNG frames + per-model JSON detections + manifest (aligned with existing report/export flow)

## Endpoint & Model Discovery
- Base URL: `http://localhost:1234/v1`
- List available models:
  - `GET /v1/models`
  - Choose a VLM that supports image understanding and follows instruction prompts (JSON-only output).
- Recommended candidates (install and run via LM Studio as available):
  - Qwen2.5-VL family — strong VLM reasoning
  - Florence-2 variants — vision understanding with tagging/localization via prompts
  - LLaVA / InternVL family — general-purpose VLMs (quality varies by checkpoint)

### UI Integration Targets (Model IDs)
- `qwen/qwen2.5-vl-7b` — Qwen2.5-VL 7B
- `zai-org/glm-4.6v-flash` — GLM 4.6v Flash

### Dashboard Controls
- The dashboard now surfaces a Vision-Language Model panel with:
  - Model selector fed by `/api/vlm/models` (local LM Studio discovery with pinned fallbacks).
  - Frame limit input (defaults to 3 frames).
  - `Run VLM` button posting to `/api/vlm/run` with `{runId, modelId, limit}` payload.
- Successful runs persist detections to the existing `InferenceRun.detections` table using the VLM’s model ID, regenerate `frame_<idx>_overlay.png`, and refresh the comparison view automatically.
- Status text reflects discovery errors, in-flight runs, or the final processed frame count.


Note: Use whatever appears in `GET /v1/models` locally. Confirm performance and format adherence before productionizing.

### Model IDs must match exactly
- LM Studio requires the `model` value to match the ID returned by `GET /v1/models` exactly.
- Different builds may use dots (`qwen2.5-vl-7b-instruct`) or underscores (`Qwen2_5-VL-7B-Instruct`). Always pick from the live list.
- If a requested model is not found, the CLI `scripts/test-vlm-app.py --list-models` will print available IDs.

## Integration Pattern
- Frame extraction (PyAV/OpenCV)
- For each sampled frame:
  - Send image + prompt to LM Studio model via OpenAI-compatible API
  - Parse JSON-only output to normalized bbox format
  - Persist detections and render overlays
- Package per-run artifacts (frames, JSON, manifest) as `run_<id>.zip` for download

## Request Structure (OpenAI-Compatible)
LM Studio supports OpenAI-style clients. Prefer the chat completions API; if your build supports the newer "responses" API, adapt accordingly.

Python (OpenAI SDK) example:
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

SYSTEM_PROMPT = (
    "You are an assistant that detects brand logos in images. "
    "Return only JSON, with fields: detections[], each with label, confidence (0-1), "
    "bbox {left, top, right, bottom} normalized to [0,1]. No extra text."
)

USER_PROMPT_TEMPLATE = (
    "Analyze the image and identify logos. "
    "Return JSON only in this schema: \n"
    "{\n  \"detections\": [\n    {\n      \"label\": \"...\",\n      \"confidence\": 0.95,\n      \"bbox\": {\"left\": 0.12, \"top\": 0.22, \"right\": 0.35, \"bottom\": 0.48}\n    }\n  ]\n}\n"
)

# Use either image URL or base64 data depending on your setup.
# With image URL:
messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT,
    },
    {
        "role": "user",
        "content": [
            {"type": "text", "text": USER_PROMPT_TEMPLATE},
            {"type": "input_image", "image_url": "http://localhost:4000/path/to/frame.jpg"}
        ],
    },
]

resp = client.chat.completions.create(
  model="<model-id-from-/v1/models>",  # pick any VLM listed by /v1/models
  messages=messages,
  temperature=0,
)
text = resp.choices[0].message.content.strip()
# Parse JSON text safely, normalize to schema used by the app.
```

If LM Studio requires base64 images, use a data URL with `image_url`:
```python
import base64, mimetypes

with open("/tmp/frame.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("ascii")
mime = mimetypes.guess_type("/tmp/frame.jpg")[0] or "image/png"
data_url = f"data:{mime};base64,{b64}"

messages = [
  {"role": "system", "content": SYSTEM_PROMPT},
  {
    "role": "user",
    "content": [
      {"type": "text", "text": USER_PROMPT_TEMPLATE},
      {"type": "image_url", "image_url": data_url}
    ],
  },
]
```

## Prompting Guidance
- Enforce "JSON-only" output, no prose.
- Require normalized bbox: `left`, `top`, `right`, `bottom` all in [0,1].
- Encourage confidence scoring (0–1 float). If absent, set a default or discard.
- For multi-logo scenes, ensure `detections` may contain multiple items.
- Add brand hints only if context allows; otherwise, keep model unbiased.

Example minimal expected response:
```json
{
  "detections": [
    {
      "label": "Metro-North Logo",
      "confidence": 0.91,
      "bbox": { "left": 0.19, "top": 0.32, "right": 0.47, "bottom": 0.58 }
    }
  ]
}
```

## Parsing & Normalization
- Accept only valid JSON; strip code fences if present.
- Validate fields; drop entries missing label or bbox.
- Map to internal schema used in the app:
  - `label`: string
  - `confidence`: float in [0,1]
  - `bbox`: normalized dict with `left`, `top`, `right`, `bottom`
  - Optionally store `bbox_2d: [x1, y1, x2, y2]` in pixels given frame size

### Practical handling for local VLMs
The helper script now accounts for a few real-world response quirks:
- **Pixel-based bboxes**: Models such as `qwen/qwen2.5-vl-7b` often emit raw pixel coordinates (see sample below). `scripts/test-vlm-app.py` reads the frame with OpenCV, derives width/height, and normalizes the values back into `[0,1]` when the bbox exceeds 1.0.
- **Alternate bbox shapes**: Both dict (`left/top/right/bottom` or `x1/y1/x2/y2`) and list (`[x1,y1,x2,y2]`) formats are accepted.
- **Malformed JSON**: If the model returns JSON-like text that fails to parse, a regex fallback splits each detection block, extracts `label`, `confidence`, and bbox numbers, then normalizes/clamps as above.
- **Confidence defaults**: Missing confidence scores are coerced to `0.0` so downstream tooling stays consistent.

Sample response captured from the Qwen run (pixel coordinates):
```json
{
  "detections": [
    {
      "label": "Phoenix Suns logo",
      "confidence": 0.95,
      "bbox": {"left": 321, "top": 476, "right": 521, "bottom": 628}
    },
    {
      "label": "FanDuel Sports Network logo",
      "confidence": 0.90,
      "bbox": {"left": 1510, "top": 225, "right": 1630, "bottom": 274}
    }
  ]
}
```
Even though the bbox fields contain integers, the script’s normalization layer converts them to the normalized schema before saving JSON or drawing overlays.

### Field result: `zai-org/glm-4.6v-flash`
- Command: `python scripts/test-vlm-app.py --run-id 43 --model-id zai-org/glm-4.6v-flash --limit 1`
- Outcome: first frame processed successfully with three detections (Fanduel, AHIA, NBA) written to [reports/run_43/json/model_B_frame_000000.json](reports/run_43/json/model_B_frame_000000.json).
- Overlay: [reports/run_43/frames/frame_000000_overlay.png](reports/run_43/frames/frame_000000_overlay.png) shows the Model B boxes in dark blue on the same frame.
- Response shape: the model preceded its JSON with `<think>...</think>` reasoning prose; the existing `extract_json_only()` helper stripped the outer text and parsed the embedded JSON without code changes, confirming resilience of the current parser.

**Agent Note — Backend Call & Parsing**
- Backend entry: the helper script in [scripts/test-vlm-app.py](scripts/test-vlm-app.py) drives the per-frame calls.
- Client setup: uses OpenAI Python client with `base_url` pointing to LM Studio (`http://localhost:1234/v1`) and a static API key (`lm-studio`).
- Message format:
  - `system` content enforces JSON-only, normalized bbox requirements.
  - `user` `content` is an array of structured parts: a `text` prompt and an `image_url` pointing to a base64 data URL.
  - If LM Studio requires nested `image_url` shape, the script retries once using `{ "image_url": { "url": data_url } }`.
- Model validation: script calls `/v1/models` to list IDs; `--list-models` prints them. It validates `--model-id` against the list and exits early if unknown.
- Logging hygiene: HTTP/OpenAI debug logs are suppressed; image base64 is never logged in full (only truncated previews when necessary in backend).
- Response parsing:
  - Reads `choices[0].message.content` text.
  - Strips surrounding code fences and language tags, then extracts the largest valid JSON object via balanced brace search.
  - Normalizes detections via type/shape checks. Invalid or out-of-range bboxes are dropped.
- Output handling:
  - Saves per-frame JSON for Model B to `reports/run_<id>/json/model_B_frame_<frame>.json`.
  - Renders overlays with Model B color (dark blue `#003366`) via [app/services/reporting_service.py](app/services/reporting_service.py).

Robust parsing tips (already implemented in the helper):
- Accept `confidence` missing by defaulting to `0.0`.
- Require bbox keys present and numeric; drop otherwise.
- Enforce normalized range [0,1] for bbox components; drop entries outside the range.
- If the model returns extra prose or formatting, the fence/brace extraction isolates the JSON payload.

Future hardening (optional):
- Add a JSON schema validator and clamp bbox values into [0,1] rather than dropping borderline cases.
- Support alternative keys (e.g., `x1,y1,x2,y2`) by mapping to normalized `bbox` when frame size is known.
- Persist a minimal diagnostics block in the JSON file (e.g., `"_meta": {"model": "...", "raw_len": N}`) to aid troubleshooting.

## Overlay Rendering
- Model A (primary) color: red `#FF0000`
- Model B (secondary) color: dark blue `#003366`
- Draw 2px stroke, label text `LABEL (confidence)` above box with a semi-transparent background (as per reporting helper).

## JSON Artifacts & Packaging
- Per-model, per-frame JSON:
  - `reports/run_<id>/json/model_A_frame_<frame>.json`
  - `reports/run_<id>/json/model_B_frame_<frame>.json`
- Optional aggregate: `reports/run_<id>/json/detections_aggregate.json`
- Overlaid PNG: `reports/run_<id>/frames/frame_<frame>_overlay.png`
- Manifest: `reports/run_<id>/manifest.json`
- Zip: `reports/run_<id>.zip` (served via `GET /api/reports/run/<id>/download`)

### Overlay artifacts
Running `python scripts/test-vlm-app.py --run-id <id> --limit <n> --model-id <model>` now produces per-frame overlays automatically (e.g., `reports/run_43/frames/frame_000000_overlay.png`). The script tags detections as Model B so the OpenCV helper draws them using the configured dark blue color.

## Configuration
- `LMSTUDIO_BASE_URL` (default `http://localhost:1234/v1`)
- `LMSTUDIO_MODEL_ID` (e.g., `Qwen2_5-VL-7B-Instruct`, must appear in `/v1/models`)
- `VLM_MAX_TOKENS`, `VLM_TEMPERATURE` (optional)

## Error Handling & Retries
- Handle timeouts and transient failures; retry 1–2 times with backoff.
- If parsing fails, re-prompt with stricter JSON-only instruction.
- Return empty `detections` with diagnostic note rather than hard-failing.

## Performance Notes
- Batch frames; limit concurrency to avoid local model overload.
- Compress frames to reasonable size (e.g., JPEG 720p) to balance speed vs accuracy.
- Cache detections when re-rendering overlays.

## Validation
- Unit tests: JSON parsing, normalization, bbox clamping.
- Integration tests: sample frames against a local VLM checkpoint; verify schema and overlays.

## Security & Privacy
- All processing is local; do not transmit frames externally.
- Avoid storing raw frames unless needed for audit; prefer overlaid outputs and JSON metadata.

## Example: Model Listing
```bash
curl -s http://localhost:1234/v1/models | jq
```
Confirm that your desired VLM appears, then set `LMSTUDIO_MODEL_ID` accordingly.

You can also use the helper CLI:
```bash
python3 scripts/test-vlm-app.py --list-models --base-url http://localhost:1234/v1
```
