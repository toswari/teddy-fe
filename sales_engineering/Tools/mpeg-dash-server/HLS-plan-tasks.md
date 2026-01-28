# HLS → DASH Tasks Checklist

## Option A: Upload HLS Files (Local `.m3u8` + `.ts`)

- [x] Backend: define HLS upload storage layout under `MEDIA_ROOT/hls/<stream-id>/`
- [x] Backend: decide upload mechanism (single ZIP vs. multiple files vs. directory sync)
- [x] Backend: implement `/api/hls/upload` (or similar) endpoint
- [x] Backend: validate uploaded content (must contain at least one `.m3u8` and matching `.ts` files)
- [x] Backend: write uploaded HLS files to `MEDIA_ROOT/hls/<stream-id>/`
- [x] Backend: implement ffmpeg call to convert uploaded HLS to DASH under `DASH_ROOT/<stream-id>/`
- [x] Backend: persist metadata for uploaded HLS streams (stream id, name, origin = "upload", mpd path, created_at, status)
- [x] Backend: return MPD path and stream metadata from upload endpoint
- [x] nginx: ensure `/dash/` is correctly mapped to `DASH_ROOT` (reusing current config)
- [x] UI: add "Upload HLS Files" section (playlist + segments / archive input)
- [x] UI: POST upload to backend, show progress / basic status
- [x] UI: on success, show generated MPD URL and add stream to registry
- [x] UI: reuse DASH player to play the generated MPD from `/dash/<stream-id>/manifest.mpd`

## Option B: Ingest Public HLS URL

- [x] Backend: define HLS stream metadata model (stream_id, name, hls_url, mpd_path, mode, status, created_at, last_error)
- [x] Backend: implement `POST /api/hls/register`
- [x] Backend: validate HLS URL (scheme http/https, .m3u8 or HLS content-type)
- [x] Backend: allocate `stream_id` and create `DASH_ROOT/<stream-id>/` directory
- [x] Backend: construct ffmpeg command to ingest HLS and output DASH manifest + segments
- [x] Backend: start ffmpeg process (Popen) and record PID / status for live mode
- [x] Backend: write metadata record to `.hls_streams.json` (or extend existing streams metadata)
- [x] Backend: return `201 Created` with stream metadata including `mpd_path`
- [x] Backend: implement `GET /api/hls/streams` to list HLS-origin streams and status
- [x] Backend: implement `DELETE /api/hls/streams/{stream_id}` to stop ingest and clean up (optional cleanup of DASH_ROOT)

## Process Management & Status

- [x] Backend: implement simple in-memory registry or PID file per stream for live ingest
- [x] Backend: capture ffmpeg stderr tail and map to `last_error` on failure
- [x] Backend: update stream `status` based on ffmpeg lifecycle (starting, running, error, stopped, completed)
- [x] Backend: surface `status` and `last_error` via `/api/hls/streams`

## UI Integration (Streamlit)

- [ ] UI: extend stream registry model with `kind: "file" | "dash" | "hls-origin" | "hls-upload"` (exact names TBD)
- [x] UI: add "Register HLS Stream" section (for public HLS URL)
- [x] UI: call `POST /api/hls/register` from the new form
- [x] UI: on success, add HLS stream to local registry with HLS URL + MPD URL
- [x] UI: display original HLS URL and generated MPD URLs (proxy + backend absolute)
- [x] UI: reuse existing `render_dash_player(...)` for HLS-origin DASH MPD playback
- [x] UI: show basic status and last error for each HLS-origin stream

## Error Handling & Validation

- [x] Backend: implement clear error responses for invalid HLS URLs / upload content
- [x] Backend: handle upstream HTTP failures (non-200, timeouts) when validating HLS URLs
- [x] Backend: ensure ffmpeg failures update metadata (`status = "error"`, `last_error` message)
- [x] UI: show validation errors and backend error messages to the user

## Persistence & Cleanup

- [x] Backend: decide whether to use dedicated `.hls_streams.json` or extend existing `.streams.json`
- [x] Backend: implement load/save helpers for HLS stream metadata
- [x] Backend: align asset retention with existing DASH retention policy (if configured)
- [x] Backend: on stream delete, optionally remove `DASH_ROOT/<stream-id>/` and/or `MEDIA_ROOT/hls/<stream-id>/`

## Verification

- [x] Local test: ingest a sample public HLS URL and confirm DASH MPD plays in the UI
- [x] Local test: upload a small HLS VOD set and confirm DASH MPD plays in the UI
- [x] Check that nginx `/dash/` serving works for new HLS-origin DASH directories
- [x] Confirm all new endpoints respect existing auth/nginx rules
ffmpeg -i "https://hd-auth.skylinewebcams.com/live.m3u8?a=86e11cp23tspnr0hnvsg" \
  -c copy -bsf:a aac_adtstoasc output.mp4
