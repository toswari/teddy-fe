## HLS → DASH (MPD) Ingest & Publish Specification

### Goal

Support HLS content ingestion and conversion to DASH in two ways:

1. **Upload HLS files**: Allow users to upload local HLS playlist files (`.m3u8`) and associated segments (`.ts` files) to the server.
2. **Ingest public HLS URLs**: Ingest a **public HLS (HTTP Live Streaming) URL** (master or media playlist) as an input stream.

Both sources are then re‑published as a **DASH MPD** served by the existing backend and nginx stack, so they can be played and diagnosed by the current DASH UI.

### High‑Level Flow

#### Option A: Upload HLS Files

1. **User uploads HLS content** in the UI:
   - Upload master/media playlist (`.m3u8`)
   - Upload associated segment files (`.ts`)
   - System stores under `MEDIA_ROOT/hls/<stream-id>/`
2. Backend converts uploaded HLS to DASH using `ffmpeg`
3. Outputs DASH assets under `DASH_ROOT/<stream-id>/`
4. nginx serves the generated DASH assets

#### Option B: Ingest Public HLS URL
	 - Output: local DASH representation (`manifest.mpd` + `.m4s` segments) under `DASH_ROOT/<stream-id>/`.
3. nginx serves the generated DASH assets under `/dash/<stream-id>/manifest.mpd`.
4. Existing **DASH diagnostics player** is reused to inspect/play the re‑published MPD.

### Functional Requirements

#### 1. Stream Registration (UI)

- Add an **HLS streams** section in the Streamlit UI:
	- Fields:
		- `Stream name` (free‑text, required).
		- `Public HLS URL` (required, must end with `.m3u8` or respond with `application/vnd.apple.mpegurl` or `application/x-mpegURL`).
	- On submit:
		- POST to new backend endpoint `/api/hls/register` with `{ name, hls_url }`.
		- Backend returns a `stream_id` and DASH `mpd_path` (relative path under `/dash/`).
	- UI should add the HLS stream to the local registry (similar to existing DASH/MP4 registry) and render a **DASH playback tab** bound to the returned MPD URL.

#### 2. Backend API

Add an HLS ingestion API in `backend/main.py`:

- `POST /api/hls/register`
	- Request body (JSON):
		- `name: str` — logical stream name.
		- `hls_url: HttpUrl | str` — public HLS master or media playlist URL.
		- Optional packaging options (initial version may ignore or hard‑code reasonable defaults):
			- `segment_duration: float` (seconds) — target DASH segment length.
			- `window_size: int` — number of segments to keep in a sliding window (for live‑style).
			- `mode: Literal["static","live"]` — whether to create a finite VOD MPD from a bounded capture window or a rolling live MPD.
	- Behavior:
		1. Validate the HLS URL (basic HEAD/GET check; must return 200 and appropriate content type or `.m3u8` extension).
		2. Allocate a unique `stream_id` (UUID or slugified name + random suffix).
		3. Compute DASH output directory: `DASH_ROOT / stream_id`.
		4. Start an **ffmpeg job** to ingest the remote HLS and output DASH:
			 - Input: `-i <hls_url>`.
			 - Output (DASH):
				 - `-use_timeline 1 -use_template 1`
				 - `-init_seg_name init-stream$RepresentationID$.m4s`
				 - `-media_seg_name chunk-stream$RepresentationID$-$Number%05d$.m4s`
				 - `-map 0:v:0 -map 0:a?`
				 - `-c:v copy -c:a copy` (initial version: remux only, no re‑encode).
				 - `-f dash <output_dir>/manifest.mpd`.
			 - For **live** mode, use: `-window_size`, `-extra_window_size`, `-remove_at_exit 1`, and `-min_seg_duration` / `-seg_duration`.
		5. Persist a **stream metadata record** (e.g. JSON file alongside `.streams.json`):
			 - `stream_id`, `name`, `hls_url`, `mpd_path`, `created_at`, `mode`, `status`.
		6. Return a response:
			 - `201 Created` on success with payload:
				 ```json
				 {
					 "stream_id": "<uuid>",
					 "name": "My HLS Stream",
					 "hls_url": "https://.../index.m3u8",
					 "mpd_path": "/dash/<stream-id>/manifest.mpd",
					 "mode": "live",
					 "status": "starting"
				 }
				 ```

- `GET /api/hls/streams`
	- Returns list of known HLS‑origin streams and their associated MPD paths and status.

- `DELETE /api/hls/streams/{stream_id}`
	- Stops any associated ffmpeg ingest process (if live) and optionally cleans up its directory under `DASH_ROOT`.

#### 3. Process Management

- For **live HLS → live DASH** mode:
	- ffmpeg must run as a **long‑lived background process** managed by the backend:
		- Option 1 (simple): spawn using `subprocess.Popen` and store PIDs in an in‑memory registry plus a PID file under the stream directory.
		- Option 2 (future): external supervisor (systemd, PM2, etc.).
	- Backend should expose basic status:
		- `status: "starting" | "running" | "error" | "stopped"`.
		- Last error message (if ffmpeg exits non‑zero).

- For **VOD capture** mode (optional MVP+):
	- Run ffmpeg **once** to capture a limited window from the HLS source and emit a finite MPD (no sliding window).
	- After completion, mark status as `"completed"` and keep assets for playback.

#### 4. nginx and URL Layout

- Reuse the existing `/dash/` nginx location:
	- HLS‑origin DASH assets live under `DASH_ROOT/<stream-id>/...` and are reachable at `/dash/<stream-id>/manifest.mpd`.
- No nginx changes are required beyond ensuring `/dash/` points to `DASH_ROOT`.

#### 5. UI Integration (Streamlit)

- Extend the stream registry model to include an **HLS origin** type:
	- Add `kind: "file" | "dash" | "hls-origin"` (exact naming TBD) per entry.
	- For HLS‑origin streams store:
		- `hls_url` — original public URL.
		- `mpd_proxy_url` — relative DASH MPD path (e.g. `/dash/<stream-id>/manifest.mpd`).
		- `mpd_backend_url` — absolute backend URL (for localhost debugging), following existing DASH URL helper conventions.

- New UI section:
	- **Register HLS Stream** form, bound to `POST /api/hls/register`.
	- On success:
		- Show a success message with the MPD URL.
		- Add an entry into the registry and immediately show a **DASH player** using the existing `render_dash_player(...)` with the `mpd_proxy_url`.

- Per‑stream page/tab:
	- Display original HLS URL and the generated MPD URLs (proxy + backend absolute), similar to existing DASH per‑stream UI.
	- Reuse diagnostics: manifest preview, request log, buffer stats, etc., via the existing DASH diagnostics player.

#### 6. Error Handling & Validation

- Validate on registration:
	- HLS URL must be HTTP/HTTPS.
	- Reject non‑`.m3u8` URLs unless content type indicates HLS playlist.
	- Surface upstream HTTP status codes and basic connectivity issues in the API response.

- Runtime errors:
	- If ffmpeg terminates unexpectedly, capture stderr tail and store as `last_error` in metadata.
	- Expose `last_error` via `/api/hls/streams` and display it in the UI.

#### 7. Persistence & Cleanup

- Metadata:
	- Store HLS‑origin stream records in a JSON file (e.g. `.hls_streams.json`) colocated with `.streams.json`, or extend the existing file to include `kind` and HLS‑specific fields.

- Assets retention:
	- Align with existing `DASH_RETENTION_DAYS` policy where applicable.
	- For live streams, implement optional **auto‑cleanup** of old directories when a stream is deleted.

### Non‑Goals (for MVP)

- No transcoding to multiple bitrates/profiles; initial implementation may **remux** only.
- No DRM, token auth, or geo‑fencing.
- No advanced HLS feature support (SCTE‑35 markers, I‑frame playlists, LL‑HLS) beyond what ffmpeg transparently consumes.

### Open Questions / TBD

- How aggressively should we retry if the HLS origin is temporarily down?
- Should we support **master playlists** with multiple variants and map them to multiple DASH adaptation sets, or restrict MVP to a single variant (first video+audio)?
- Do we need quota/limits on concurrent HLS‑origin streams per deployment?

