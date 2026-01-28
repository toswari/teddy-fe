# MPEG-DASH Packaging Tasks

Actionable checklist for enabling and validating MP4 → MPD (MPEG-DASH) packaging.

## Backend
- [x] Ensure `ffmpeg` is installed and discoverable in `PATH` on all environments.
- [x] Implement `_ensure_ffmpeg_available` to guard `/api/dash/package` when ffmpeg is missing.
- [x] Implement `_package_to_dash(source, output_dir)` using `ffmpeg -f dash` to write `manifest.mpd` + segments.
- [x] Mount `DASH_ROOT` at `/dash` via `StaticFiles` so manifests/segments are HTTP-accessible.
- [x] Implement `POST /api/dash/package`:
  - [x] Validate `path` with `_resolve_and_validate` (under `MEDIA_ROOT`, `.mp4`, exists).
  - [x] Accept optional `stream_id` to provide stable DASH output directory names.
  - [x] Return relative `manifest` path and `output_dir` (both relative to `DASH_ROOT`).
- [x] Drop unsupported metadata streams (e.g., GoPro `gpmd`) during packaging to avoid ffmpeg copy failures.
- [x] Add `/api/media` endpoint to enumerate all MP4 and MPD assets (relative + absolute paths, sizes, timestamps).
  - Server URL: `http://localhost:8000/api/media` lists every streamable MP4 and published MPD directly from the backend.
  - MPD entries include a `url` field pointing at the fully-qualified `/dash/<manifest>` URL for client playback.
- [x] Add backend tests for `/api/dash/package` success + failure cases (ffmpeg missing, invalid path, non-MP4, etc.).

## UI (Streamlit)
- [x] Add **Package to DASH** control in **Manage Streams** section.
- [x] POST to `/api/dash/package` with `{"path": stream.filePath, "stream_id": stream.streamId}`.
- [x] Store `dashManifest` and `dashPackagedAt` in `.streams.json` on success.
- [x] Add **MPEG-DASH** tab per stream that:
  - [x] Initializes dash.js with `BACKEND_URL + "/dash/" + dashManifest`.
  - [x] Shows copyable MPD URL.
- [x] Add **Quick Player** tab for MPD:
  - [x] Let user select MPD from `DASH_ROOT` or paste arbitrary MPD URL.
  - [x] Render via dash.js in the UI.
- [x] Surface clearer errors in UI on packaging failure, including ffmpeg stderr snippet when available.
- [x] Add inline playback diagnostics inspired by the reference livestream player: dash.js stats (bitrate, buffer, dropped frames), MPD text preview, and quick reload/reset buttons under the MPEG-DASH tab.

## Configuration & Scripts
- [x] Support `DASH_ROOT` via `.env` and default to `MEDIA_ROOT/dash`.
- [x] Document MPD packaging workflow in `README.md` and `package-mpd-plan.md`.
- [x] Add optional script/Make target to pre-package a sample MP4 for local testing (invoking `/api/dash/package` or ffmpeg directly).
- [x] Add HTTPS termination guidance + config (e.g., nginx/Caddy or uvicorn `--ssl-keyfile/--ssl-certfile`) so `/api`, `/dash`, and `/video` are accessible over TLS in non-local environments.
- [ ] Update Streamlit/CLI instructions to point to the HTTPS backend URL by default and confirm the UI can load MPDs without mixed-content warnings.

## Validation
- [x] Manual backend test: curl `POST /api/dash/package` + curl MPD URL from `/dash`.
- [x] Manual UI test: upload MP4 → add stream → package → play via MPEG-DASH tab.
- [ ] External player test: open produced MPD in an independent dash.js player or DASH-capable video player. _(Run manually; see README "CLI Helper" for MPD URLs.)_
- [ ] Large file test: package and play a longer MP4 to validate performance and segmenting behavior. _(Run manually with any >5 min MP4.)_

## DASH Parity Improvements
- [x] Prototype a live-style packaging mode (MPD `type="dynamic"`, `minimumUpdatePeriod`, `timeShiftBufferDepth`) using ffmpeg flags like `-streaming 1`, `-window_size`, and `-extra_window_size` so our output can mirror streams such as https://video-livestream-staging.clarifai.com/livestream/people_1920_1080_30fps.mpd.
- [x] Make segment template/padding configurable (e.g., toggle `%05d` numbering vs. `$Number$`) to align segment URIs with external manifests when needed.
- [x] Add an optional re-encode path to target higher video bitrates (≈5 Mbps) instead of the current `-c:v copy`, ensuring parity with reference assets.

## Operations
- [x] Add metric counters/log parsing for `/api/dash/package` latency and failure rate.
- [x] Decide and implement retention policy for `DASH_ROOT` (e.g., periodic cleanup job).
- [x] If using Azure, wire `MEDIA_ROOT`/`DASH_ROOT` to a shared volume (Azure Files) and consider offloading metadata to Azure Cosmos DB. _(Documented in README production notes.)_
