# MP4 Streaming Service + Streamlit UI

**Demo Tool:** This tool simulates live streaming for the Video Intelligence feature of Clarifai Platform.

FastAPI serves MP4 content with HTTP range support and exposes DASH packaging; Streamlit provides a control panel for managing, packaging, and playing streams.

## Prerequisites
- Python 3.9+
- `ffmpeg` available on `PATH` (for MP4 → DASH packaging)
- Local `.mp4` files you can place under `media/` or upload through the UI

## Quick Start
```bash
./setup-env.sh        # creates .venv, installs deps, writes .env, makes media/
./start-servers.sh    # launches backend (FastAPI) + UI (Streamlit)
```
The start script automatically loads `.env`, checks for port conflicts, starts both services, and opens the UI in your browser (set `AUTO_OPEN_UI=0` to disable). Stop both services with:
```bash
./stop-servers.sh
```
Debug logging is enabled by default (`LOG_LEVEL=DEBUG` in `.env.example`) so you can observe packaging diagnostics immediately.

## Manual Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # adjust MEDIA_ROOT/BACKEND_PORT/UI_PORT as needed
```
Launch the backend and UI manually if you prefer (binding to all interfaces):
```bash
MEDIA_ROOT="$(pwd)/media" uvicorn backend.main:app --host 0.0.0.0 --port 8000
# new terminal
MEDIA_ROOT="$(pwd)/media" BACKEND_URL="http://localhost:8000" streamlit run ui/streamlit_app.py --server.address 0.0.0.0
```

## HTTPS via nginx on port 5443
`setup-env.sh` can now provision an nginx reverse proxy (listening on 5443) and request a Let's Encrypt certificate via the bundled `letsenscript.sh` helper. Point a public DNS record at your host, ensure ports 80 and 5443 are reachable, then run:

```bash
./setup-env.sh --setup-nginx --tls-domain stream.example.com --tls-email ops@example.com
```

The script will:
- Install nginx + certbot (Homebrew on macOS, apt on Debian/Ubuntu/WSL).
- Run `letsenscript.sh` (a thin wrapper around `certbot certonly --standalone`) to issue certificates for the supplied domain.
- Write an nginx config that terminates TLS on `https://<domain>:5443`, serves `/dash/` from `MEDIA_ROOT/dash`, proxies `/api` + `/video` to the FastAPI backend (port 8000), and forwards `/` to the Streamlit UI (port 8501).
- Streamlit’s embedded dash.js players now request manifests and segments via relative URLs, so playback works end-to-end through the HTTPS proxy without mixed-content failures.
- Reload nginx so the site is immediately available.

### Manual certificate issuance + renewal

`letsenscript.sh <domain> <email> [extra certbot args…]` issues or renews a certificate using certbot’s standalone HTTP-01 flow:
- First run: calls `certbot certonly --standalone --http-01-port 80` with `-d <domain>` and the supplied email.
- Subsequent runs detect `/etc/letsencrypt/live/<domain>` and invoke `certbot renew --cert-name <domain> --force-renewal --standalone`, so the same lineage persists.
- Pass `LETSENSCRIPT_HTTP_PORT=8080 ./letsenscript.sh …` if you must bind to an alternate port (remember to forward that port externally during issuance).

For automated renewals, rely on certbot’s built-in `renew` command (already used by `letsenscript.sh` for single domains) or schedule it via cron/systemd, e.g.:

```bash
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet --deploy-hook 'sudo systemctl reload nginx'") | crontab -
```

Every renewal reuses the HTTP-01 standalone authenticator, so ensure nothing else listens on port 80 when the job runs (use `--pre-hook "systemctl stop nginx"` / `--post-hook "systemctl start nginx"` if needed).

Tune the listener/paths via environment variables (`HTTPS_PORT`, `TLS_DOMAIN`, `TLS_EMAIL`, `BACKEND_PORT`, `UI_PORT`, `DASH_ROOT`). Re-run the command whenever you need to push config changes; it is idempotent and will skip certificate issuance if the domain already has material under `/etc/letsencrypt/live/<domain>`.

### Password-protecting the UI (nginx basic auth)

When using nginx as a reverse proxy, you can enable HTTP Basic Auth to require a username and password for access:

1. **Create an htpasswd file** (one-time setup):
   ```bash
   sudo htpasswd -c /etc/nginx/.htpasswd-mpeg-dash myuser
   # Enter password when prompted
   ```

2. **Enable auth in nginx config**:
   - Edit `nginx-config-reference.conf` and ensure the server block includes:
     ```nginx
     auth_basic "Restricted";
     auth_basic_user_file /etc/nginx/.htpasswd-mpeg-dash;
     ```
   - Public endpoints (`/dash/*`, `/api/media`, `/healthz`) include `auth_basic off;` so DASH playback and health checks work without credentials.

3. **Apply the config**:
   ```bash
   ./update-nginx-config.sh
   ```

4. **Logout**: Click the 🔒 Logout button in the sidebar to clear browser credentials, or use an incognito window for each session.

The UI automatically detects the browser's origin (localhost vs HTTPS) and sets the backend URL accordingly, so no manual configuration is needed when switching between development and production access.

## Configuration
- `.env.example` lists default values; copy to `.env` for local overrides.
- `MEDIA_ROOT` defaults to `./media`; the repo keeps an empty directory only (no sample media is committed). Supply your own MP4s or upload via the UI.
- DASH outputs are written beneath `DASH_ROOT` (default `MEDIA_ROOT/dash`) and are served by the backend at `/dash/<manifest>.mpd`.
- `DASH_RETENTION_DAYS` (default `0`) prunes packaged outputs older than the specified number of days every time a new packaging job completes.
- `LOG_LEVEL` defaults to `DEBUG` so ffmpeg/stdout diagnostics are visible; override it in `.env` if you prefer quieter logs.

## Using the UI
- **Backend URL auto-detection**: When accessing the UI via `https://your-domain:5443`, the backend URL is automatically set to match. For localhost development (`http://localhost:8501`), it defaults to `http://localhost:8000`.
- Upload MP4 files and register named streams stored in `MEDIA_ROOT/.streams.json`.
- **Stream Management**: Each registered stream shows:
  - MP4 playback tab with video player
  - MPEG-DASH tab (available after packaging)
  - Stream metadata (file size, bitrate, creation time)
- Trigger **Package to DASH** (requires `ffmpeg`) to generate segments + MPD; dash.js playback becomes available under the MPEG-DASH tab.
- Expand **Advanced packaging options** to:
	- Produce live-style (`type="dynamic"`) manifests with adjustable segment duration and window sizes.
	- Override init/media segment templates and padding so filenames match external conventions.
	- Re-encode streams (libx264 + AAC) at configurable bitrates when source assets need higher quality than direct copy.
- **Sidebar tools**:
  - View backend health status and media root path
  - Access the [View all streams (API)] link to see `/api/media` JSON output
  - Click 🔒 Logout to clear authentication when using password-protected nginx
- Diagnostics panel issues test requests against `/video` with optional Range headers.
- Backend health is polled from `/healthz`; status and resolved paths are shown in the sidebar.
- Packaging automatically skips non audio/video metadata streams (e.g., GoPro GPMD) so ffmpeg can complete successfully; those telemetry tracks are not included in the DASH output.
- **Security**: Video URLs use relative paths (e.g., `video?path=filename.mp4`) instead of absolute server paths to avoid exposing directory structure. The backend validates all paths to ensure they stay within `MEDIA_ROOT`.

## API Helpers
- `GET /api/media` — returns every MP4 under `MEDIA_ROOT` and every MPD under `DASH_ROOT`, including absolute paths, relative paths, sizes, and modified timestamps. Handy for driving automation or validating available assets without scraping the filesystem. Example: visit `http://localhost:8000/api/media` once the backend is running to see the full inventory as JSON.
- `POST /api/dash/package` — triggers ffmpeg-based packaging (see CLI helper below) and surfaces stderr snippets when something fails. Supply an optional `options` object to request live/dynamic manifests, tweak segment naming, or force libx264/AAC re-encoding with explicit bitrates.

### CLI Helper
- Run `./package-sample.sh <path-to-mp4>` to trigger packaging via the backend without opening the UI.
- Flags: `--backend-url`, `--stream-id`, `--dynamic`, `--segment-duration`, `--window-size`, `--extra-window-size`, `--segment-padding`, `--segment-template`, `--init-template`, `--reencode`, `--video-bitrate`, `--audio-bitrate`.
- Example (live-style manifest with re-encode):
	```bash
	./package-sample.sh media/sample.mp4 \
		--dynamic --segment-duration 4 --window-size 6 --extra-window-size 6 \
		--segment-template 'people_1920_1080_30fps_chunk_$RepresentationID$_$Number$.m4s' \
		--init-template 'people_1920_1080_30fps_init_$RepresentationID$.m4s' \
		--reencode --video-bitrate 5500 --audio-bitrate 192
	```
- The script validates the MP4 path, builds the JSON payload (including `options`), and prints the backend response with any ffmpeg stderr snippets when failures occur.

## Testing
```bash
pytest -q
```

## Notes
- Only files inside `MEDIA_ROOT` are served; path traversal attempts return `403`.
- CORS is enabled so the Streamlit frontend can reach the FastAPI backend.
- `ffmpeg` is required at runtime for DASH packaging (`brew install ffmpeg` or `sudo apt install ffmpeg`).
- For production, front the backend with a reverse proxy and place media on durable storage (object store or shared volume).
- `/api/dash/package` now emits timing metrics and success/failure counters (see `/healthz -> packaging_metrics`) so you can feed them into log-based monitoring.
- Set `DASH_RETENTION_DAYS` to enforce a rolling cleanup of packaged assets; combine with cron/Task Scheduler if you need stricter retention guarantees.
- On Azure, mount `MEDIA_ROOT`/`DASH_ROOT` to Azure Files or BlobFuse and persist stream metadata in Azure Cosmos DB (e.g., partition by `tenantId` or `streamId`) for global scale.

## Production Considerations
- **Reverse proxy**: Terminate TLS and route traffic through NGINX, Apache, or Azure Front Door. Sample NGINX snippet:
  ```nginx
  server {
	  listen 443 ssl;
	  server_name stream.example.com;
	  location /api/ {
		  proxy_pass http://backend-service:8000/;
		  proxy_set_header Host $host;
		  proxy_set_header X-Real-IP $remote_addr;
	  }
	  location / {
		  proxy_pass http://ui-service:8501/;
	  }
  }
  ```
- **Scaling backend**: Run multiple FastAPI instances behind the proxy and use sticky routing only if you keep in-memory state. The backend is stateless; horizontal scale is safe once media resides on shared storage.
- **Media storage**: Offload MP4s and DASH artifacts to Azure Blob Storage or another object store mounted via Azure Files/NFS. Keep `MEDIA_ROOT` pointed at the mounted volume so uploads remain compatible.
- **Metadata**: Store stream metadata in Azure Cosmos DB (partition by `tenantId` or `streamId`) when you move beyond the local JSON registry. Cosmos DB offers multi-region writes and low-latency lookups for AI/chat use cases and stream catalogs alike.
- **Environment management**: Promote `.env` values to Azure App Service or container orchestrator secrets; never commit real credentials. Use unique `BACKEND_URL` per environment and set `AUTO_OPEN_UI=0` on headless servers.
- **Process supervision**: Package backend/UI as systemd services, Docker containers, or Azure Container Apps. Add health probes against `/healthz` and configure restart policies.
- **Observability**: Forward logs to Azure Monitor or Application Insights. Capture `handled request` entries from the backend and Streamlit server logs; add metrics for request latency and packaging outcomes.
- **Security**: Enable HTTPS, restrict upload size at the proxy, and consider API authentication (API keys or JWT) before mutating endpoints like `/api/dash/package` in production.

### Password-protecting the UI (nginx basic auth)

If you are fronting the app with nginx (via `setup-env.sh --setup-nginx`), you can enable HTTP Basic Auth on the Streamlit UI without changing any Python code:

- Create an htpasswd file on the server (first run uses `-c` to create the file):
	```bash
	sudo htpasswd -c /etc/nginx/.htpasswd-mpeg-dash myuser
	# enter a strong password when prompted
	```
- Set the following environment variables before running `./setup-env.sh --setup-nginx` (or export them and re-run that step to regenerate the config):
	```bash
	export UI_BASIC_AUTH=1
	export UI_BASIC_AUTH_REALM="Restricted"
	export UI_BASIC_AUTH_FILE="/etc/nginx/.htpasswd-mpeg-dash"
	./setup-env.sh --setup-nginx --tls-domain stream.example.com --tls-email ops@example.com
	```

When `UI_BASIC_AUTH=1` is set, the generated nginx config will add `auth_basic` and `auth_basic_user_file` directives on the `/` location that proxies to Streamlit. Browsers will prompt for `myuser` and its password before any part of the UI is served. To turn this off later, set `UI_BASIC_AUTH=0` and re-run the nginx setup step, then reload nginx.
