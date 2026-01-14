#!/usr/bin/env bash

set -euo pipefail

# Start local web application (FastAPI/uvicorn) directly on the host
# and use podman/docker only to start the database containers.
#
# Optional environment variables (set in your shell or .env):
#   export CLARIFAI_PAT=your_pat_here   # or CLARIFAI_API_KEY
#   export PORT=8081                    # override default 8080 if busy

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8080}"

echo "[start-servers] Project root: $ROOT_DIR"
echo "[start-servers] Target web port: $PORT"

start_databases() {
  echo "[start-servers] Starting database containers (postgres-db, classifai-db) if available..."

  if command -v podman >/dev/null 2>&1; then
    echo "[start-servers] Using podman to start DB containers"
    podman start postgres-db classifai-db 2>/dev/null || echo "[start-servers] Warning: podman containers postgres-db/classifai-db not found or not startable"
    return
  fi

  if command -v docker >/dev/null 2>&1; then
    echo "[start-servers] Using docker to start DB containers"
    docker start postgres-db classifai-db 2>/dev/null || echo "[start-servers] Warning: docker containers postgres-db/classifai-db not found or not startable"
    return
  fi

  echo "[start-servers] No podman or docker found; skipping database startup"
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

  # Run uvicorn from the project root so relative paths (uploads/projects) match
  python -m uvicorn src.web.app:app --host 0.0.0.0 --port "$PORT"
}

main() {
  start_databases
  setup_venv
  start_web_app
}

main "$@"
