# Clarifai API Playbook

This document distills the latest Clarifai inference guidance for coding agents who are wiring video/logo detection inside VideoLogoDetection. Use it alongside `ImplementationTaskPlan.md`, `docs/api-examples.md`, and `app/services/inference_service.py` when you begin integrating real models.

## 1. Prerequisites

- Install the official SDK in the project env (already listed in `requirements.txt`). Reinforce via:
  ```bash
  pip install --upgrade clarifai
  ```
- Generate a Personal Access Token (PAT) in Clarifai Console → Settings → Secrets. Export it _before_ running the Flask app so `create_app()` can pick it up:
  ```bash
  export CLARIFAI_PAT=your_pat_here
  ```
- No extra infra is required: the SDK talks directly to Clarifai over HTTPS/gRPC. Keep everything in-process per the MVP directives (no Celery/Redis).

## 2. Model Client Patterns

The SDK revolves around `clarifai.client.Model`. Initialize it with either IDs or the canonical URL. Dedicated deployments require an extra identifier (see §2.2).

```python
from clarifai.client import Model

LOGO_MODEL_URL = "https://clarifai.com/your_user/your_app/models/logo-detector"

model = Model(
    url=LOGO_MODEL_URL,
    # deployment_id="custom_runner_id",           # optional dedicated deployment
    # compute_cluster_id="cluster_id",            # alternative orchestration knobs
    # nodepool_id="nodepool_id",
)
```

### 2.1 Version Pinning

- Latest version is used automatically.
- Supply `model_version={"id": "version_id"}` or append `/versions/<version_id>` to the URL when you must pin reproducible runs.

### 2.2 Dedicated Deployments vs Shared SaaS

- Featured models (e.g., OpenAI/Gemini wrappers) run on Clarifai Shared SaaS without extra config.
- Custom or fine-tuned logo detectors must be **deployed** first. Pass one of:
  - `deployment_id="deployment_guid"`
  - or `compute_cluster_id` + `nodepool_id`
  - If the deployment belongs to another user/org, add `deployment_user_id`.

## 3. Input Helpers (Image / Video / Frame Batches)

Import the typed helpers from `clarifai.runners.utils.data_types` to keep code concise:

```python
from clarifai.runners.utils.data_types import Image, Video
```

| Use Case             | Helper                                      | Notes |
|----------------------|---------------------------------------------|-------|
| Frame bytes          | `Image(bytes=frame_bytes)`                  | Perfect for PyAV/OpenCV pipelines. |
| Frame from disk      | `Image.from_pil(pillow_img)`                | Keeps metadata. |
| Remote frame sample  | `Image(url="https://.../frame.jpg")`       | Useful for smoke tests. |
| Entire clip/segment  | `Video(bytes=clip_bytes)` or `Video(url=...)` | Enables stream/track models (SAM2, etc.). |

## 4. Prediction Modes

### 4.1 Unary (single request → single response)

Ideal for syncing sampled frames generated during Phase 1.

```python
from clarifai.client import Model
from clarifai.runners.utils.data_types import Image

model = Model(url=LOGO_MODEL_URL)

response = model.predict(
    inputs=[
        {
            "image": Image(bytes=frame_bytes),
            "metadata": {"video_id": video_id, "ts": frame_ts},
        }
    ],
    inference_params={
        "max_concepts": 5,
        "min_value": 0.2,
    },
)
```

- Pass a **list** of inputs to batch multiple frames; the SDK automatically treats single dicts as singleton batches.
- Each result contains `outputs[i].data.regions` with bounding boxes, concepts, track IDs, etc.

### 4.2 Streaming (`model.generate`)

Use streaming when a single video segment yields many intermediate outputs (e.g., SAM2 tracking example in the Clarifai docs).

```python
from clarifai.runners.utils.data_types import Video

for chunk in model.generate(
    video=Video(bytes=clip_bytes),
    inference_params={"return_type": "all"}
):
    handle_stream_chunk(chunk)
```

Handle stream chunks incrementally to update Socket.IO progress without blocking the Flask request thread.

### 4.3 Asynchronous Helpers

- `await model.async_predict(...)` submits work without blocking; integrate with `asyncio.run()` inside simple worker threads if you need concurrency later.
- `await model.async_generate(...)` yields streamed chunks asynchronously.

## 5. Response Handling Cheatsheet

| Field                           | Location                                   | Usage in this repo |
|---------------------------------|--------------------------------------------|--------------------|
| Detection concepts              | `region.concepts`                          | Persist to JSONB `results` and/or `Detection` table. |
| Bounding/segmentation mask      | `region.region_info.bounding_box` or `region.mask` | For overlay previews in the UI. |
| Confidence                      | `concept.value`                            | Use for thresholding and metrics. |
| Track ID (video)                | `region.track_id`                          | Map detections across frames. |
| Request metadata (debug)        | `proto.status.req_id` (when `with_proto=True`) | Log for support and retriable jobs. |

Enable raw protobuf inspection only when debugging:

```python
result, proto = model.predict(..., with_proto=True)
logger.info("Clarifai req_id=%s status=%s", proto.status.req_id, proto.status.code)
```

## 6. Error Handling & Retries

- SDK raises `grpc.RpcError` or `requests.HTTPError` depending on the transport. Wrap calls in try/except and surface actionable errors via the Flask API.
- For long videos, keep batches small (e.g., ≤32 frames) to avoid `RESOURCE_EXHAUSTED`.
- On rate-limit or timeout, back off exponentially (2s, 4s, 8s) before retrying the batch.

## 7. Integrating with VideoLogoDetection Services

1. **Frame Sampler** (`video_service.py`): emit `(frame_bytes, timestamp)` iterables.
2. **Inference Service** (`inference_service.py`):
   - Initialize `Model` once per run to amortize gRPC handshakes.
   - Batch frames and call `model.predict()`.
   - Normalize Clarifai `Region` objects into the repo’s canonical detection structure.
3. **Persistence**:
   - Store raw Clarifai payloads (truncated) in `InferenceRun.results` (JSONB) for audits.
   - Derive lightweight summaries (top concepts, bounding boxes) for the UI and reports.
4. **Progress Updates**:
   - Emit Socket.IO events per batch; include `req_id` for traceability.

## 8. Testing & Local Smoke Checks

- Use the snippets in `docs/api-examples.md` to verify the Flask endpoints before wiring Clarifai calls.
- For SDK validation without the web app, run:
  ```bash
  python - <<'PY'
  import os
  from clarifai.client import Model
  from clarifai.runners.utils.data_types import Image

  os.environ.setdefault("CLARIFAI_PAT", "your_pat_here")
  model = Model(url="https://clarifai.com/openai/chat-completion/models/o4-mini")
  print(model.predict("Describe Clarifai"))
  PY
  ```
- When Clarifai is unreachable, stub `Model` with a fake client that emits deterministic detections so the rest of the stack keeps working.

## 9. Checklist Before Shipping Clarifai Integrations

- [ ] `CLARIFAI_PAT` is injected via `.env` or the host shell (never hardcode).
- [ ] `requirements.txt` pins a compatible `clarifai` package version.
- [ ] `inference_service.py` exposes single-model and multi-model helpers per Implementation Task Plan §1.6/2.1.
- [ ] Socket.IO events surface inference status and Clarifai request IDs for debugging.
- [ ] Tests or scripts cover: model init, batch predict, error handling, and proto logging toggle.

Reference docs consulted: [Clarifai Inference via API](https://docs.clarifai.com/compute/inference/clarifai/api) and [Clarifai Python SDK Reference](https://docs.clarifai.com/resources/api-references/python).