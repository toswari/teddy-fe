# Software Specification — MP4/DASH Streaming Backend (FastAPI)

## 1. Overview
- Purpose: Provide an HTTP service to stream local `.mp4` files, package them into MPEG-DASH outputs, and expose lightweight catalog APIs (media listing, health) using a FastAPI backend.
- Scope: Secure file streaming with byte-range support, ffmpeg-backed DASH packaging, on-disk manifest/segment hosting, media inventory inspection, and baseline observability. CDN integration and multi-bitrate ladders remain future work.

## 2. Goals & Non-Goals
- Goals:
	- Serve `.mp4` over HTTP with `Content-Type: video/mp4` and robust Range handling.
	- Enforce strict path validation under an allowed `MEDIA_ROOT`.
	- Provide ffmpeg-powered DASH packaging via `/api/dash/package`, including manifest hosting under `/dash`, structured diagnostics, and automated retention of generated artifacts.
	- Expose `/api/media` to enumerate available `.mp4` and `.mpd` assets so UI clients (Streamlit, CLI) can present accurate catalogs.
	- Capture basic metrics (request counters, packaging duration, cleanup activity) and emit DEBUG-level logs for troubleshooting.
	- Provide simple auth (optional) and basic observability hooks.
- Non-Goals (initial release):
	- Real-time transcoding, multiple renditions, or per-title ladder optimization.
	- DRM license serving.
	- Multi-tenant catalog persistence backed by an external datastore (future: Azure Cosmos DB).

## 3. Functional Requirements
- MP4 Streaming Endpoint:
	- Method: `GET`
	- Path: `/video`
	- Query: `path` (absolute or relative to `MEDIA_ROOT`)
	- Headers: Optional `Range: bytes=start-end`
	- Behavior:
		- If `Range` provided, return `206 Partial Content` with `Content-Range`, `Accept-Ranges: bytes`, and the requested chunk.
		- If no `Range`, return `200 OK` with full file stream.
		- Always set `Content-Type: video/mp4`.
	- Errors:
		- `400 Bad Request` for missing/invalid `path`.
		- `403 Forbidden` for path traversal or file outside `MEDIA_ROOT`.
		- `404 Not Found` if file does not exist.
		- `416 Range Not Satisfiable` for invalid range.

- DASH Packaging & Streaming:
	- Packaging:
		- Method: `POST`
		- Path: `/api/dash/package`
		- Body: JSON with the following parameters:
			- `path`: MP4 file path (required)
			- `stream_id`: Optional stream identifier
			- `mode`: "static" or "dynamic" (default: "dynamic") - Controls MPD type for live/on-demand streaming
			- `segment_duration`: Seconds per segment (default: 4)
			- `window_size`: Rolling window for live streaming (default: 5 segments)
			- `minimum_update_period`: Seconds between manifest updates for dynamic mode (default: 8.0)
			- `suggested_presentation_delay`: Client buffer delay in seconds (default: 8.0)
			- `time_shift_buffer_depth`: DVR window in seconds (default: 3600.0)
		- Behavior:
			- Validate input MP4 via the same path rules as `/video`.
			- Invoke `ffmpeg` (singleton per request) to map only audio/video streams (`-map 0:v -map 0:a?`), preventing metadata tracks (e.g., GoPro GPMD) from causing packaging failures.
			- For dynamic mode, use `-streaming 1 -ldash 1 -update_period <value>` to configure live streaming parameters.
			- Post-process the generated MPD manifest to convert type from "static" to "dynamic" and inject live streaming attributes: `availabilityStartTime`, `publishTime`, `minimumUpdatePeriod`, `suggestedPresentationDelay`, `timeShiftBufferDepth`.
			- Persist DASH outputs under `DASH_ROOT/<stream_id or timestamp>` and record packaging duration, bytes produced, and stderr diagnostics.
			- On success, return `200 OK` with JSON `{ "manifest": "<relative mpd path>", "output_dir": "<relative dir>", "logs": "<stderr excerpt>" }` so clients can surface ffmpeg output.
			- After each successful run, enqueue retention cleanup to remove directories older than the configured TTL.
			- On failure, return `500` with `{ "detail": "Packaging failed", "logs": "<stderr excerpt>" }`.
		- Errors: `400`/`403`/`404` from path validation, `500` for failed packaging or missing manifest.
		- Standards Compliance: Adheres to ISO/IEC 23009-1:2012 (MPEG-DASH), uses isoff-live:2011 profile for dynamic manifests.
	- Static MPD/Segment Serving:
		- Mount `DASH_ROOT` at `/dash` using static file serving.
		- MPD URL pattern: `/dash/<subdir>/manifest.mpd` (used by UI and external clients).
	- Metrics & Retention:
		- Increment counters (`dash_packages_total`, `dash_failures_total`).
		- Histogram/summary for packaging duration.
		- Background job periodically deletes packaged directories older than the retention window (default 60 minutes, configurable).

- Media Inventory Endpoint:
	- Method: `GET`
	- Path: `/api/media`
	- Behavior:
		- Recursively scan `MEDIA_ROOT` for `.mp4` files and `DASH_ROOT` for `.mpd` manifests.
		- Return JSON `{ "mp4": [...], "mpd": [...] }` where each entry contains a relative path, file size, and last-modified timestamp.
		- Optionally filter results via query params (e.g., `suffix`, `limit`) if provided.
	- Errors:
		- `500` for filesystem access errors (surface message + log diagnostics).
	- Use cases:
		- Populate Streamlit dropdowns.
		- Power automation scripts that verify packaging results.

- Health Endpoint:
	- `GET /healthz` → `200 OK` with basic service info.

- Optional Auth:
	- API key via header `X-API-Key` or Bearer token.
	- Deny if key/token missing or invalid (feature flag).

## 4. Non-Functional Requirements
- Performance: Efficient chunked I/O; target low latency for initial playback (<150 ms for header + first chunk under typical local conditions).
- Scalability: Support at least 100 concurrent streams plus on-demand packaging jobs on a single node (assuming local disk throughput and network capacity).
- Availability: Single-instance acceptable initially; production recommends multiple replicas behind reverse proxy.
- Security: Directory traversal prevention, restrictive allowed roots, optional auth, no arbitrary command execution.
- Observability: DEBUG-level structured logs for streaming and packaging paths, FastAPI middleware timers, `ffmpeg` stderr capture, metrics export (requests, failures, packaging duration, cleanup counts).
- Compliance: Log rotation; avoid storing PII.

## 5. API Contract
- `GET /video?path=REL_OR_ABS_PATH`
	- Request Headers:
		- `Range` (optional): `bytes=<start>-<end>`.
		- `Authorization` (optional): `Bearer <token>`.
		- `X-API-Key` (optional): `<key>`.
	- Success Responses:
		- `200 OK` (no range):
			- Headers: `Content-Type: video/mp4`, `Accept-Ranges: bytes`, `Content-Length`.
			- Body: full file stream.
		- `206 Partial Content` (with range):
			- Headers: `Content-Type: video/mp4`, `Accept-Ranges: bytes`, `Content-Range: bytes <start>-<end>/<filesize>`, `Content-Length`.
			- Body: requested byte slice.
	- Error Responses:
		- `400`, `403`, `404`, `416` as per requirements.

- `GET /healthz`
	- `200 OK` with `{ "status": "ok" }`.

- `POST /api/dash/package`
	- Request Body:
		```
		{
		  "path": "/var/media/sample.mp4",
		  "stream_id": "sample",
		  "mode": "dynamic",
		  "segment_duration": 4,
		  "window_size": 5,
		  "minimum_update_period": 8.0,
		  "suggested_presentation_delay": 8.0,
		  "time_shift_buffer_depth": 3600.0
		}
		```
	- Success `200 OK`:
		```
		{
		  "manifest": "dash/sample/manifest.mpd",
		  "output_dir": "dash/sample",
		  "logs": "ffmpeg stderr snippet",
		  "duration_ms": 8421
		}
		```
	- Generated MPD attributes (dynamic mode):
		- `type="dynamic"`: Indicates live/simulated-live streaming
		- `availabilityStartTime`: ISO 8601 timestamp of packaging start
		- `publishTime`: ISO 8601 timestamp of manifest generation
		- `minimumUpdatePeriod`: Client refresh interval (e.g., "PT8S")
		- `suggestedPresentationDelay`: Recommended buffer delay (e.g., "PT8S")
		- `timeShiftBufferDepth`: DVR window duration (e.g., "PT3600S")
	- Error `400`/`403`/`404`: path validation failures.
	- Error `500`: includes `{ "detail": "Packaging failed", "logs": "ffmpeg stderr" }`.

- `GET /api/media`
	- Success `200 OK`:
		```
		{
		  "mp4": [
		    { "path": "samples/ocean.mp4", "size_bytes": 104857600, "modified": "2024-04-15T12:03:22Z" }
		  ],
		  "mpd": [
		    { "path": "dash/ocean/manifest.mpd", "size_bytes": 24567, "modified": "2024-04-15T12:05:44Z" }
		  ]
		}
		```
	- Errors `500` for filesystem read failures.

### Example Usage
```
curl -v "http://localhost:8000/video?path=/var/media/sample.mp4"
curl -v -H "Range: bytes=0-1023" "http://localhost:8000/video?path=/var/media/sample.mp4"
```

## 6. Data & Storage
- Media Files: Reside under `MEDIA_ROOT` directory (configurable).
- DASH Outputs: Stored under `DASH_ROOT/<stream>/` alongside segments and `manifest.mpd`; retention worker prunes directories older than the configured TTL.
- Metrics & Logs: Exposed via in-memory counters and log files/streams; integrate with Azure Monitor or Prometheus for production.
- Metadata: Not required initially. When catalog persistence is needed, use Azure Cosmos DB (global distribution, multi-region writes). Choose a high-cardinality partition key such as `videoId` or `tenantId`, or adopt Hierarchical Partition Keys for tenant/asset combos to avoid hot partitions.

## 7. Configuration
- Environment Variables:
	- `MEDIA_ROOT`: Absolute path to the allowed media directory (required).
	- `DASH_ROOT`: Absolute path for MPEG-DASH outputs (default: `<MEDIA_ROOT>/dash`).
	- `DASH_RETENTION_MINUTES`: Minutes to retain packaged outputs before automated cleanup (default: `60`). Set to `0` to disable deletion.
	- `API_KEY` or `AUTH_JWT_PUBLIC_KEY`: Optional for auth.
	- `CHUNK_SIZE_BYTES`: Optional stream chunk size (default: `1_048_576`).
	- `LOG_LEVEL`: `DEBUG` by default to surface packaging diagnostics; raise to `INFO` for production.
	- `METRICS_SAMPLE_RATE` (optional): Controls frequency of emitting packaging/streaming metrics to logs.

## 8. Implementation Details (FastAPI)
- Range Handling:
	- Parse `Range` header (`bytes=start-end`). Validate start/end within file size.
	- Compute `Content-Range` and `Content-Length` for the slice.
	- Use `StreamingResponse` to yield chunk(s) from a file handle.
	- Always set `Accept-Ranges: bytes`.

- Path Validation:
	- Resolve the requested path: `resolved = Path(MEDIA_ROOT) / Path(requested).name` for relative inputs or normalize absolute with `Path(requested).resolve()`.
	- Ensure `resolved.is_file()` and `resolved.is_relative_to(MEDIA_ROOT)` (or fallback check via string prefix) to prevent traversal.

- MIME Type:
	- Force `Content-Type: video/mp4` (or detect via `mimetypes` and validate).

- DASH Packaging:
	- Construct ffmpeg command with explicit stream selection (`-map 0:v -map 0:a?`) and `-adaptation_sets` to avoid metadata tracks.
	- For dynamic mode, add streaming flags: `-streaming 1 -ldash 1 -update_period <minimum_update_period>`.
	- Post-process generated MPD manifest using XML parsing (xml.etree.ElementTree):
		- Convert `type` attribute from "static" to "dynamic"
		- Inject live streaming attributes: `availabilityStartTime`, `publishTime`, `minimumUpdatePeriod`, `suggestedPresentationDelay`, `timeShiftBufferDepth`
		- Remove `mediaPresentationDuration` attribute (incompatible with dynamic mode)
		- Preserve namespace declarations and formatting
	- Capture stdout/stderr; include stderr in API responses for transparency.
	- Run packaging in a subprocess with timeout safeguards and propagate non-zero exit codes as `500` responses.
	- Record metrics (duration, success/failure) and log structured events for observability.
	- Trigger background cleanup after each run; cleanup walks `DASH_ROOT` and deletes directories older than the retention threshold.

- Media Inventory:
	- Traverse `MEDIA_ROOT`/`DASH_ROOT` using `Path.rglob` (depth-limited to prevent runaway scans).
	- Build response models with normalized relative paths, file sizes, and ISO timestamps.
	- Cache results briefly (optional) to avoid repeated disk scans under heavy UI polling.

- Logging & Debug:
	- Global middleware logs method, path, status, duration (ms), bytes sent, Range header, client IP.
	- DEBUG logs include path resolution, range parsing, ffmpeg command lines, subprocess exit codes, cleanup actions, and media inventory scan stats.

## 9. Security Considerations
- Restrict serving to `MEDIA_ROOT` only; disallow symlinks outside root.
- Validate all inputs; sanitize query params.
- Optional auth via API key/JWT.
- Avoid exposing filesystem structure in errors.

## 10. Deployment
- Local: `uvicorn app:app --host 0.0.0.0 --port 8000`.
- Production:
	- Run behind NGINX or a cloud load balancer.
	- Enable HTTP/1.1 keep-alive; consider HTTP/2.
	- Mount `MEDIA_ROOT` on fast storage (NVMe or network storage with sufficient throughput).
	- Horizontal scale with multiple replicas; sticky sessions not required.

## 11. Testing Strategy
- Unit:
	- Range parser (valid, open-ended, invalid ranges).
	- Path validation (inside/outside root, traversal attempts).
- Integration:
	- End-to-end stream for a known `.mp4` with and without `Range`.
	- Verify headers and statuses (`200`, `206`, `416`).
- Browser test:
	- HTML `<video>` element can seek and play via `/video` endpoint.

## 12. Observability & Diagnostics
- Emit structured logs for slow requests (>500 ms), ffmpeg invocations, and cleanup tasks, including diagnostic strings provided by the Azure Cosmos DB SDK if/when it is introduced for metadata.
- Publish counters for `/video`, `/api/dash/package`, and `/api/media` (total, success, failure) plus histograms for packaging duration.
- Surface `ffmpeg` stderr in API responses/UI to accelerate debugging.
- If using Cosmos DB for metadata/analytics, enable SDK diagnostics for latency anomalies and `429` retries; log partition key and RU consumption when troubleshooting.

## 13. Acceptance Criteria
- Serving a valid `.mp4` returns `200 OK` with correct headers; Range requests yield `206 Partial Content`.
- Invalid ranges return `416`; paths outside `MEDIA_ROOT` return `403`.
- `POST /api/dash/package` packages a valid MP4, returns manifest/output paths, includes stderr logs, and leaves artifacts under `/dash/<stream>/manifest.mpd`.
- Packaging failures surface `500` with stderr context while protecting internal filesystem paths.
- Retention job deletes packaged directories older than the configured TTL (verified via integration test or manual inspection).
- `GET /api/media` lists both MP4 and MPD assets with accurate metadata; endpoints handle empty states gracefully.
- Health endpoint returns `200` consistently.

## 14. Future Enhancements
- ✅ **Completed**: Dynamic/Live DASH manifests with ISO/IEC 23009-1:2012 compliance
- HLS packaging and manifests (m3u8 generation)
- Multi-bitrate ladder (adaptive streaming with multiple quality levels)
- Real-time transcoding pipeline for on-the-fly encoding
- CDN integration with signed URLs for secure distribution
- Subtitles (WebVTT) and multiple audio tracks for accessibility
- Access control per tenant/user; catalog API backed by Cosmos DB
- True live streaming with continuous segment generation (current: simulated-live from VoD)

## 15. Glossary
- Range Request: HTTP mechanism allowing clients to request partial content to enable seeking.
- `206 Partial Content`: Status code indicating a successful range response.
- `Content-Range`: Response header denoting the served byte range and total size.

## 16. UI Requirements — Streamlit Interface

### Purpose
- Provide a simple control panel to upload/select `.mp4` files under `MEDIA_ROOT` and play them via the backend `/video` endpoint.

### Functional Requirements
- Server Settings:
	- Sidebar input for backend base URL (default `http://localhost:8000`).
	- Health indicator calling `GET /healthz` and displaying status and resolved `MEDIA_ROOT`.
- File Management:
	- Upload single `.mp4` files into `MEDIA_ROOT`.
	- List available `.mp4` files (recursive under `MEDIA_ROOT`).
	- Select a file to preview.
- Quick Player:
	- Provide a dedicated section to quickly play content without managing streams.
	- MP4 mode:
		- Dropdown listing all `.mp4` files under `MEDIA_ROOT` for selection.
		- On selection, render an HTML5 `<video>` bound to `/video?path=<selected>`.
		- Display the MP4 URL as a copyable text value for external use.
	- DASH mode:
		- Dropdown listing all `*.mpd` files under `DASH_ROOT`.
		- Allow entering an arbitrary MPD URL (e.g., remote manifest) in a text field.
		- On selection or input, render a dash.js player configured with the chosen MPD.
		- Display the effective MPD URL as a copyable text value for external clients.
- Player:
	- For each configured stream, embed HTML5 `<video>` pointing to `/video?path=<absolute or resolved path>` for MP4 streaming.
	- Show the direct MP4 stream URL link for debugging.
	- Support seeking (leveraging backend Range responses).
	- Provide a second player mode for MPEG-DASH playback using dash.js, bound to the stored MPD URL per stream.
- Feedback & Errors:
	- Display clear messages for missing/invalid path, forbidden path, not found, and range errors.
	- Re-check health on demand.

#### Stream Management
- Concept: A "stream" is a named entry linking to an `.mp4` file path under `MEDIA_ROOT`.
- Add Stream:
	- Form with fields: `Stream Name` (required, unique), `File` (picker from available files or upload).
	- Creates/updates a local registry (JSON file under `MEDIA_ROOT/.streams.json` or in-memory) of streams: `{ streamId, name, filePath, createdAt }`.
- Delete Stream:
	- Remove the stream from the registry with confirmation.
	- Do not delete the underlying file by default; provide an optional checkbox `Also delete file` (unchecked by default).
- List Streams:
	- Table/cards showing name, file, size, and quick actions (Play, Delete).
- Play Multiple Streams:
	- Allow multi-select to open multiple independent players, each sourcing from `/video?path=<stream.filePath>`.
	- Render in a responsive grid (e.g., 2–4 columns) with individual controls and status per player.
	- Cap simultaneous players via a configurable limit (default: 4) to avoid resource exhaustion; show a warning when limit reached.
	- Each player displays bitrate (approx bytes/sec from recent chunks) and basic stats (elapsed, buffered if available).

- DASH Packaging Controls:
	- Per-stream action "Package to DASH" to call backend `/api/dash/package` with the stream’s MP4 path and ID.
	- Configuration options:
		- Packaging Mode: Checkbox for "Dynamic/Live Manifest" (default: enabled)
		- Segment Duration: Number input for seconds per segment (default: 4)
		- Window Size: Number of segments in rolling window (default: 5)
		- Live Streaming Parameters (conditional, shown when dynamic mode enabled):
			- Minimum Update Period: Client manifest refresh interval in seconds (default: 8.0)
			- Suggested Presentation Delay: Client buffer delay in seconds (default: 8.0)
			- Time Shift Buffer Depth: DVR window in seconds (default: 3600.0)
		- Info tooltips explaining each parameter's purpose and impact on streaming behavior
	- Show packaging progress, surface ffmpeg stderr/log excerpts from the API response, and persist success/failure state.
	- On success, store MPD relative path and timestamp in the stream registry and mark entries as "packaged".
	- For each packaged stream, display a clearly labeled, copyable MPD URL that external clients can use.
	- Support switching between MP4 and DASH playback per stream (e.g., via UI tabs) and ensure the DASH dropdown is powered by `/api/media` so freshly generated manifests appear without reloads.
	- DASH player uses dash.js with support for both static and dynamic manifests, including live edge seeking and DVR functionality.

### Non-Functional Requirements
- Usability: Minimal, responsive layout; primary actions visible in one screen.
- Performance: Initial playback should start quickly; render without heavy client-side processing.
- Security: Do not expose directory listings outside `MEDIA_ROOT`; sanitize paths shown in UI.
- Compatibility: Target recent Chrome, Firefox, and Safari on macOS; Edge/Chrome on Windows/WSL2.
- Observability: Log basic UI actions (health check success/failure, selected file) to console; optional server-side analytics.

- Concurrency: Support multiple simultaneous players with smooth playback; avoid blocking UI interactions while streams are active.

### Configuration
- Environment variables:
	- `BACKEND_URL`: default backend base URL shown in the sidebar.
	- `MEDIA_ROOT`: local directory for uploads and file discovery.
- Defaults: If unset, `BACKEND_URL = http://localhost:8000`, `MEDIA_ROOT = ./media`.
- Stream Registry:
	- Default path: `MEDIA_ROOT/.streams.json` (file-based), or fallback to in-memory if write is not permitted.
	- Schema: Array of stream objects `{ streamId: string, name: string, filePath: string, createdAt: ISO8601 }`.

### Accessibility
- Keyboard-accessible file picker and player controls.
- Sufficient contrast for status badges; readable fonts.

### Acceptance Criteria
- Health indicator reflects backend status via `/healthz`.
- Upload places files under `MEDIA_ROOT` and surfaces them in the list.
- Selecting a file renders the player and streams from `/video` with seek support.
- UI prevents or warns on invalid files and paths.
- Adding a stream persists it to the registry; it appears in the list with Play/Delete actions.
- Deleting a stream removes it from the registry (file remains unless explicitly chosen to delete).
- Multi-selecting streams renders multiple players concurrently with independent controls.

### Future Enhancements
- Catalog view with thumbnails, duration, and metadata.
- Multi-tenant isolation and role-based access.
- Optional metadata and analytics storage in Azure Cosmos DB (recommend high-cardinality partition keys such as `tenantId` or `videoId`; consider Hierarchical Partition Keys for scale and flexible queries).
- Backend endpoints for stream registry (optional): `GET /streams`, `POST /streams`, `DELETE /streams/{id}` to support multi-user scenarios and persistence beyond local UI state.