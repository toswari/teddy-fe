# MPEG-DASH Packaging Plan (MP4 → MPD)

This document captures what needs to be in place for the MPD packaging feature to work reliably end-to-end.

## 1. Prerequisites
- **ffmpeg installed and on PATH**
  - macOS: `brew install ffmpeg`
  - Ubuntu/WSL2: `sudo apt update && sudo apt install -y ffmpeg`
- **Python environment**
  - Use the project venv created by `./setup-env.sh` or:
    - `python -m venv .venv`
    - `source .venv/bin/activate`
    - `pip install -r requirements.txt`
- **Config via .env** (or direct env vars)
  - `MEDIA_ROOT` (directory with MP4 inputs; default `./media`)
  - `DASH_ROOT` (output directory for DASH artifacts; default `MEDIA_ROOT/dash`)
  - `BACKEND_PORT` (default `8000`)
  - `UI_PORT` (default `8501`)
  - `BACKEND_URL` (usually `http://localhost:${BACKEND_PORT}`)
  - `LOG_LEVEL=DEBUG` while validating.

## 2. Backend Requirements
- Endpoint: `POST /api/dash/package`
  - Request body: `{ "path": "<absolute-or-media-relative-mp4-path>", "stream_id": "<optional-stream-id>" }`
    - Optional `options` object enables packaging profiles:
      ```json
      {
        "path": "media/sample.mp4",
        "stream_id": "sample-stream",
        "options": {
          "mode": "dynamic",
          "segment_duration_seconds": 4,
          "window_size": 6,
          "extra_window_size": 6,
          "segment_padding": 0,
          "segment_template": "people_1920_1080_30fps_chunk_$RepresentationID$_$Number$.m4s",
          "init_segment_template": "people_1920_1080_30fps_init_$RepresentationID$.m4s",
          "reencode": true,
          "video_bitrate_kbps": 5500,
          "audio_bitrate_kbps": 192
        }
      }
      ```
    - `mode`: `static` (default) produces VOD-style MPDs; `dynamic` enables live-style manifests (`type="dynamic"`, streaming flags, configurable window sizes, optional `-ldash`).
    - `segment_padding`: controls `$Number` formatting (default `5`, set to `0` to emit `$Number$`). `segment_template` / `init_segment_template` let you match external naming conventions exactly.
    - `reencode`: toggles libx264 + AAC re-encoding with optional bitrate targets when source material needs higher bitrates than the incoming MP4.
  - Behavior:
    - Validates path via `_resolve_and_validate` (must be under `MEDIA_ROOT`, must exist, extension `.mp4`).
    - Ensures `ffmpeg` is available (fails with 500 if missing).
    - Drops non audio/video tracks (e.g., telemetry streams such as GoPro `gpmd`) so ffmpeg can copy inputs without re-encoding or failing.
    - Calls `_package_to_dash(source, output_dir)`:
      - Cleans/creates `output_dir` under `DASH_ROOT`.
      - Runs `ffmpeg` with `-f dash` to generate `manifest.mpd` and segments.
    - Endpoint: `GET /api/media`
      - Purpose: inventory all MP4 (source) and MPD (packaged) assets without touching the filesystem manually.
      - Returns: arrays of objects with relative path (within `MEDIA_ROOT`/`DASH_ROOT`), absolute path, size (bytes), and last-modified timestamp.
      - For MPD entries, also includes a `url` field that resolves to `http(s)://<backend-host>:<port>/dash/<manifest-path>` so clients can consume the MPD directly.
      - Example response (trimmed):
        ```json
        {
          "mp4": [
            {
              "path": "NEW Microsoft AI Update is INSANE!.mp4",
              "absolute_path": "/.../media/NEW Microsoft AI Update is INSANE!.mp4",
              "size_bytes": 90650140,
              "modified_at": "2026-01-27T14:23:12.189852Z"
            }
          ],
          "mpd": [
            {
              "path": "9eb3700d5c64488f92f4bf526686950f/manifest.mpd",
              "absolute_path": "/.../media/dash/9eb3700d5c64488f92f4bf526686950f/manifest.mpd",
              "size_bytes": 4020,
              "modified_at": "2026-01-27T14:56:13.573535Z",
              "url": "http://localhost:8000/dash/9eb3700d5c64488f92f4bf526686950f/manifest.mpd"
            }
          ]
        }
        ```
      - Use cases: UI dropdown population, external automation, smoke tests, or CLI tooling.
    - Returns JSON: `{ "manifest": "<relative-path-from-DASH_ROOT>", "output_dir": "<relative-dir-from-DASH_ROOT>" }`.
- Static serving:
  - `DASH_ROOT` is mounted at `/dash` in `backend/main.py`:
    - Manifest URL format: `http://<backend-host>:<port>/dash/<manifest-relative-path>`.
- Logging:
  - On success: `packaged DASH manifest=<...> source=<...> output=<...>`.
  - On failure: logs ffmpeg stderr and returns HTTP 500.

## 3. UI Flow (Streamlit)
- **Upload & register stream**
  1. Go to the UI (default `http://localhost:8501`).
  2. Use **Upload MP4** to add a file into `MEDIA_ROOT`.
  3. Under **Add Stream**, choose a name and select the uploaded MP4.
  4. Save stream → stream metadata is written to `MEDIA_ROOT/.streams.json`.
- **Trigger packaging**
  1. In **Manage Streams**, locate the stream.
  2. Click **Package to DASH**.
  3. UI sends `POST /api/dash/package` with the stream's `filePath`, `streamId`, and any advanced options selected in the **Advanced packaging options** expander (dynamic/live MPD, segment naming overrides, re-encode bitrates).
  4. On success, UI stores the returned manifest path in the stream (`dashManifest`) and rerenders.
  5. Future enhancement: enrich MPEG-DASH playback tabs with quick controls and diagnostics inspired by the reference livestream player (stats panel, MPD preview, reload/reset buttons).
- **Playback & URLs**
  - Each stream shows:
    - **MP4 tab**: direct `/video` playback.
    - **MPEG-DASH tab**: dash.js player initialized with `BACKEND_URL + "/dash/" + manifest`.
    - Copyable MPD URL for use in external DASH players.
    - TODO: add inline dash.js stats and manifest preview, plus quick reload/reset controls mirroring the reference DASH player UI.
  - Packaging errors bubble up with ffmpeg stderr snippets so users understand what failed.

## 4. Manual Testing Checklist
- **Backend only**
  1. Ensure backend is running: `curl -s http://localhost:8000/healthz`.
  2. Place a small MP4 under `MEDIA_ROOT` (e.g. `media/sample.mp4`).
  3. Call packaging endpoint:
     ```bash
     curl -X POST \
       -H "Content-Type: application/json" \
       -d '{"path": "media/sample.mp4"}' \
       http://localhost:8000/api/dash/package
     ```
  4. Confirm JSON response contains `manifest` and folder exists under `DASH_ROOT`.
  5. Hit manifest directly:
     ```bash
     curl -I "http://localhost:8000/dash/<manifest-from-response>"
     ```

- **UI end-to-end**
  1. Start everything with `./start-servers.sh`.
  2. Confirm health in sidebar (status OK, media_root shown).
  3. Upload an MP4 and add a stream.
  4. Click **Package to DASH** and wait for success.
  5. Switch to **MPEG-DASH** tab and verify playback.
  6. Copy the MPD URL and open it in a standalone dash.js player or another DASH-capable client.

## 5. Error Handling & Debugging
- If **ffmpeg missing**:
  - Backend returns 500 (`ffmpeg is required for DASH packaging`); install ffmpeg and restart.
- If **path invalid or outside MEDIA_ROOT**:
  - `_resolve_and_validate` returns 403/404; verify `MEDIA_ROOT` and path passed from UI.
- If **ffmpeg command fails**:
  - Backend logs `ffmpeg packaging failed: <stderr>` at ERROR level and returns the stderr tail in the HTTP response so the UI can display it.
- If **dash.js fails to play**:
  - Check developer console network tab for MPD/segment 404 or CORS issues.
  - Confirm manifest path under `DASH_ROOT` matches `/dash/<manifest>` URL.

## 6. Production Notes (MPD-specific)
- Terminate TLS and expose both backend (`/api`, `/dash`) and the Streamlit UI over **HTTPS** so browsers and external DASH clients can load manifests/segments without mixed-content errors. Use a reverse proxy (nginx/Caddy), managed ingress, or uvicorn/Streamlit SSL flags, and ensure MPD URLs in responses/UI reflect the `https://` scheme.
- Use durable/shared storage (e.g., Azure Blob + Azure Files mount) behind `MEDIA_ROOT`/`DASH_ROOT` so packaged assets survive restarts and can be served from multiple replicas.
- Consider pre-packaging frequently used streams offline rather than on-demand for heavy traffic.
- Monitor:
  - Count of `/api/dash/package` calls and their latency.
  - ffmpeg failures vs successes.
  - Storage consumption under `DASH_ROOT` (add retention/cleanup policy).
- Set `DASH_RETENTION_DAYS` to let the backend automatically prune stale DASH artifacts after each successful packaging job.
- Use the CLI helper `./package-sample.sh` for smoke tests or automation pipelines without launching the Streamlit UI.
