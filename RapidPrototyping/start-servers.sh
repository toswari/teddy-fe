#!/usr/bin/env bash

set -euo pipefail

# Start local web application (FastAPI/uvicorn) directly on the host.
# No external database is required for this application.
#
# Optional environment variables (set in your shell or .env):
#   export CLARIFAI_PAT=your_pat_here   # or CLARIFAI_API_KEY
#   export PORT=8081                    # override default 8080 if busy

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8080}"

echo "[start-servers] Project root: $ROOT_DIR"
echo "[start-servers] Target web port: $PORT"

ensure_port_free() {
  local port="$PORT"

  if command -v lsof >/dev/null 2>&1; then
    echo "[start-servers] Checking if port $port is in use..."
    # Use requested command to terminate any processes on the port
    # Note: If xargs -r is unavailable on your system, fallback logic is handled below.
    if ! lsof -t -i :"$port" | xargs -r kill -9 2>/dev/null; then
      # Fallback: manually collect PIDs and kill if xargs -r isn't supported
      local pids
      pids="$(lsof -t -i TCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
      if [[ -n "$pids" ]]; then
        echo "[start-servers] Port $port is in use by PID(s): $pids"
        echo "[start-servers] Killing PID(s) on port $port with -9..."
        kill -9 $pids 2>/dev/null || echo "[start-servers] Warning: failed to kill PID(s) $pids" >&2
        sleep 1
      fi
    else
      echo "[start-servers] Freed port $port successfully."
      sleep 1
    fi
  else
    echo "[start-servers] lsof not found; cannot automatically free port $port" >&2
  fi
}

setup_venv() {
  local venv_dir="${VENV_DIR:-$ROOT_DIR/venv}"

  if [[ ! -d "$venv_dir" ]]; then
    echo "[start-servers] Creating virtual environment at $venv_dir"
    python3 -m venv "$venv_dir"
  fi

  # shellcheck disable=SC1090
  source "$venv_dir/bin/activate"

  echo "[start-servers] Installing/updating Python dependencies"
  pip install --upgrade pip >/dev/null
  pip install -r "$ROOT_DIR/requirements.txt"
}

start_web_app() {
  echo "[start-servers] Starting FastAPI app with uvicorn on port $PORT"

  # Prefer explicit CLARIFAI_API_KEY; fall back to CLARIFAI_PAT if set
  if [[ -z "${CLARIFAI_API_KEY:-}" && -n "${CLARIFAI_PAT:-}" ]]; then
    export CLARIFAI_API_KEY="$CLARIFAI_PAT"
  fi

  if [[ -z "${CLARIFAI_API_KEY:-}" && -z "${CLARIFAI_PAT:-}" ]]; then
    echo "[start-servers] WARNING: No CLARIFAI_API_KEY or CLARIFAI_PAT found in the environment; ensure .env or env vars are configured" >&2
  fi

  export PYTHONPATH="$ROOT_DIR"

  # Ensure the target port is free before starting uvicorn
  ensure_port_free

  # Run uvicorn from the project root so relative paths (uploads/projects) match
  python -m uvicorn src.web.app:app --host 0.0.0.0 --port "$PORT"
}

main() {
  setup_venv
  start_web_app
}

main "$@"
