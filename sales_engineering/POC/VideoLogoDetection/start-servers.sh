#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "${SCRIPT_DIR}"

RUNTIME_DIR="${SCRIPT_DIR}/tmp/runtime"
PID_DIR="${RUNTIME_DIR}/pids"
LOG_DIR="${SCRIPT_DIR}/tmp/logs"
FLASK_PID_FILE="${PID_DIR}/flask.pid"
FLASK_LOG_FILE="${LOG_DIR}/flask.log"
COMPOSE_FILE="${SCRIPT_DIR}/podman-compose.yaml"

mkdir -p "${PID_DIR}" "${LOG_DIR}"

log_info() {
  printf '[INFO] %s\n' "$1"
}

log_warn() {
  printf '[WARN] %s\n' "$1"
}

log_error() {
  printf '[ERROR] %s\n' "$1" >&2
}

# Ensure previous stack is stopped before starting anew to avoid stale PIDs/containers.
if [[ -x "${SCRIPT_DIR}/stop-servers.sh" ]]; then
  log_warn "Stopping any existing stack before startup."
  "${SCRIPT_DIR}/stop-servers.sh" >/dev/null 2>&1 || true
fi

while [[ $# -gt 0 ]]; do
  log_error "Unknown option: $1"
  exit 1
done

build_compose_command() {
  if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(podman-compose)
    return 0
  fi
  if command -v podman >/dev/null 2>&1; then
    COMPOSE_CMD=(podman compose)
    return 0
  fi
  return 1
}

if ! build_compose_command; then
  log_error "Neither podman-compose nor podman compose is available."
  exit 1
fi

log_info "Using compose command: ${COMPOSE_CMD[*]}"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  log_info "Loading environment from .env"
  set -a
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.env"
  set +a
fi

log_info "Starting database container"
if "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" up -d; then
  log_info "Container stack is starting."
else
  log_error "Failed to launch container stack."
  exit 1
fi

if [[ -f "${FLASK_PID_FILE}" ]]; then
  EXISTING_PID=$(cat "${FLASK_PID_FILE}" || true)
  if [[ -n "${EXISTING_PID}" ]] && ps -p "${EXISTING_PID}" >/dev/null 2>&1; then
    log_warn "Flask server already running with PID ${EXISTING_PID}."
    log_warn "Skipping Flask launch; stop it first if you need a restart."
    exit 0
  fi
fi

log_info "Starting Flask development server"
export FLASK_APP=run.py
export APP_ENV=${APP_ENV:-development}

nohup "${SCRIPT_DIR}/start.sh" >"${FLASK_LOG_FILE}" 2>&1 &
FLASK_PID=$!

echo "${FLASK_PID}" >"${FLASK_PID_FILE}"
log_info "Flask server launched with PID ${FLASK_PID}. Logs: ${FLASK_LOG_FILE}"

log_info "Open http://localhost:5000/ in your browser to use the dashboard."

log_info "Tailing Flask logs (Ctrl+C to stop tailing only):"
tail -n 20 -f "${FLASK_LOG_FILE}" || log_warn "Unable to tail Flask log." 
