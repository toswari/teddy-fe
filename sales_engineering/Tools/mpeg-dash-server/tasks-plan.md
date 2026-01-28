# Project Tasks Plan — MP4 Streaming Service

This checklist tracks work items across backend, UI, scripts, testing, and deployment. Tick items as you complete them.

## Backend (FastAPI)
- [x] Scaffold backend with CORS and health endpoint — see backend/main.py
- [x] Implement `GET /video` with byte-range support
- [x] Add unit tests for range parsing (`206`, `416`, open-ended ranges)
- [x] Add path validation tests (inside/outside `MEDIA_ROOT`, traversal attempts)
- [x] Add basic request logging (path, range, status, duration, bytes served)
- [x] Add DASH packaging endpoint (`POST /api/dash/package`)
- [x] Serve DASH assets via `/dash` static mount
- [x] Use `ffmpeg` as the MP4 → MPEG-DASH packager (invoked via subprocess)
- [ ] Optional: expose `GET /streams`, `POST /streams`, `DELETE /streams/{id}` for registry persistence

## UI (Streamlit)
- [x] Upload/select/play single MP4 — see ui/streamlit_app.py
- [x] Sidebar server URL + `/healthz` status
- [x] Stream registry (file-based) at `MEDIA_ROOT/.streams.json` (save/load)
- [x] Stream management: Add, Delete (with confirmation; optional delete file)
- [x] Multi-stream playback: grid layout with independent players (limit default 4)
- [x] Display basic per-player stats (elapsed; approx bitrate)
- [x] Error surfaces: invalid path, forbidden, not found, range errors
- [x] Trigger DASH packaging from UI
- [x] Add dash.js-based MPD playback (MP4/DASH tabs per stream)
- [x] Show copyable MPD URL in UI for external clients
- [x] Add Quick Player to select and play arbitrary MP4s and MPDs

## Scripts & Tooling
- [x] Environment setup — setup-env.sh (macOS/WSL2)
- [x] Start/Stop helpers — start-servers.sh, stop-servers.sh
- [x] Port conflict detection with friendly messages
- [x] Auto-open UI in browser on start (optional)
- [x] Add `.env` loading convenience in UI/backend (optional)

## Configuration & Docs
- [x] Specification updated with backend + UI requirements — SoftwareSpec.md
- [x] Dependencies — requirements.txt
- [ ] README: expand production notes (reverse proxy, scaling, storage)
- [x] Add example `.env` template and usage notes
- [x] Document DASH packaging workflow (ffmpeg requirement, MPD endpoints)

## Testing
- [x] Add pytest + test harness
- [x] Backend integration tests (`/video` full and partial responses)
- [ ] UI smoke test for health and single playback (headless where feasible)
- [x] Avoid bundling media assets; document how to provide test MP4s locally

## Deployment
- [ ] Dockerfile for backend and UI
- [ ] Docker Compose (backend + UI + volume for media)
- [ ] Optional: NGINX/Reverse proxy config sample

## Observability
- [ ] Structured logging and basic counters (requests, statuses, bytes)
- [ ] Latency diagnostics for slow requests (>500 ms)

## Stretch Goals
- [ ] Catalog view with thumbnails/duration metadata
- [ ] Multi-tenant isolation and auth
- [ ] Azure Cosmos DB for metadata/analytics (partition key: `tenantId` or `videoId`; consider HPK)
- [ ] HLS/DASH packaging; ABR ladder; CDN integration
