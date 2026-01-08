#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "${SCRIPT_DIR}"

RUNTIME_DIR="${SCRIPT_DIR}/tmp/runtime"
PID_DIR="${RUNTIME_DIR}/pids"
FLASK_PID_FILE="${PID_DIR}/flask.pid"
COMPOSE_FILE="${SCRIPT_DIR}/podman-compose.yaml"

log_info() {
  printf '[INFO] %s\n' "$1"
}

log_warn() {
  printf '[WARN] %s\n' "$1"
}

log_error() {
  printf '[ERROR] %s\n' "$1" >&2
}

stop_flask() {
  if [[ ! -f "${FLASK_PID_FILE}" ]]; then
    log_warn "No Flask PID file found; skipping Flask shutdown."
    return
  fi
  local pid
  pid=$(cat "${FLASK_PID_FILE}" || true)
  if [[ -z "${pid}" ]]; then
    log_warn "Flask PID file empty; removing it."
    rm -f "${FLASK_PID_FILE}"
    return
  fi
  if ! ps -p "${pid}" >/dev/null 2>&1; then
    log_warn "No process found for Flask PID ${pid}; removing stale PID file."
    rm -f "${FLASK_PID_FILE}"
    return
  fi
  log_info "Stopping Flask server (PID ${pid})"
  kill "${pid}"
  for _ in {1..10}; do
    if ! ps -p "${pid}" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ps -p "${pid}" >/dev/null 2>&1; then
    log_warn "Flask server still running; sending SIGKILL."
    kill -9 "${pid}" || true
  fi
  rm -f "${FLASK_PID_FILE}"
  log_info "Flask server stopped."
}

stop_db() {
  local compose_cmd
  if command -v podman-compose >/dev/null 2>&1; then
    compose_cmd=(podman-compose)
  elif command -v podman >/dev/null 2>&1; then
    compose_cmd=(podman compose)
  else
    log_error "Neither podman-compose nor podman compose is available."
    return
  fi
  log_info "Using compose command: ${compose_cmd[*]}"
  log_info "Stopping database container"
  if "${compose_cmd[@]}" -f "${COMPOSE_FILE}" down >/dev/null 2>&1; then
    log_info "Database container stopped."
  else
    log_warn "Failed to stop database container; it may not be running."
  fi
}

stop_flask
stop_db
