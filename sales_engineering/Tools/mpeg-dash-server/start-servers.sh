#!/usr/bin/env bash
# Start FastAPI backend and Streamlit UI in background with PID tracking
# Works on macOS and WSL2 Ubuntu

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
VENVDIR="$ROOT_DIR/.venv"
ENV_FILE="$ROOT_DIR/.env"

mkdir -p "$RUN_DIR"

# Load .env if present (overridable via existing environment variables)
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

LOG_LEVEL="${LOG_LEVEL:-DEBUG}"
export LOG_LEVEL

MEDIA_ROOT_DEFAULT="${MEDIA_ROOT_DEFAULT:-$ROOT_DIR/media}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
UI_PORT="${UI_PORT:-8501}"
AUTO_OPEN_UI="${AUTO_OPEN_UI:-1}"
SKIP_PORT_CHECK="${SKIP_PORT_CHECK:-0}"
HTTPS_PORT="${HTTPS_PORT:-5443}"
START_NGINX="${START_NGINX:-0}"
PUBLIC_HTTPS_ORIGIN="${PUBLIC_HTTPS_ORIGIN:-https://clarifai-lab.ddns.net:5443}"
export PUBLIC_HTTPS_ORIGIN

# Activate venv if present
if [[ -d "$VENVDIR" ]]; then
  # shellcheck disable=SC1091
  source "$VENVDIR/bin/activate"
fi

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: '$cmd' not found. Run setup-env.sh first." >&2
    exit 1
  fi
}

require_cmd uvicorn
require_cmd streamlit

run_privileged() {
  if [[ $EUID -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    "$@"
  fi
}

port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -PiTCP:"$port" -sTCP:LISTEN -t 2>/dev/null
    return 0
  elif command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $0}'
    return 0
  elif command -v netstat >/dev/null 2>&1; then
    netstat -an 2>/dev/null | awk -v p=":$port" '$4 ~ p && /LISTEN/ {print $0}'
    return 0
  fi
  return 1
}

kill_port_holders() {
  local port="$1" label="$2"
  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  local IFS=$'\n'
  local pids_raw
  pids_raw="$(lsof -PiTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -z "$pids_raw" ]]; then
    return 1
  fi
  local pids=($pids_raw)
  echo "Port $port busy before starting $label; terminating stale processes: ${pids[*]}"
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 10); do
    sleep 0.2
    pids_raw="$(lsof -PiTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
    if [[ -z "$pids_raw" ]]; then
      return 0
    fi
    pids=($pids_raw)
  done
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
  sleep 0.2
  pids_raw="$(lsof -PiTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -z "$pids_raw" ]]; then
    return 0
  fi
  return 1
}

check_port_free() {
  local port="$1" name="$2"
  if [[ "$SKIP_PORT_CHECK" == "1" ]]; then
    return
  fi
  local result
  result=$(port_in_use "$port") || true
  if [[ -z "$result" ]]; then
    return
  fi
  if kill_port_holders "$port" "$name"; then
    sleep 0.2
    result=$(port_in_use "$port") || true
    [[ -z "$result" ]] && return
  fi
  cat <<EOF >&2
Error: Port $port already in use before starting $name.
Details: $result
Resolve the conflict manually or set SKIP_PORT_CHECK=1 to bypass.
EOF
  exit 1
}

MEDIA_ROOT="${MEDIA_ROOT:-$MEDIA_ROOT_DEFAULT}"
BACKEND_URL="${BACKEND_URL:-}" # if empty, will derive from BACKEND_PORT
if [[ -z "$BACKEND_URL" ]]; then
  BACKEND_URL="http://localhost:$BACKEND_PORT"
fi

mkdir -p "$MEDIA_ROOT"

start_process() {
  local name="$1"; shift
  local pidfile="$RUN_DIR/$name.pid"
  local logfile="$RUN_DIR/$name.log"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "$name is already running (PID $(cat "$pidfile"))."
    return 0
  fi
  echo "Starting $name ..."
  : >"$logfile"
  "$@" \
    > >(tee -a "$logfile") \
    2> >(tee -a "$logfile" >&2) &
  local pid=$!
  echo "$pid" >"$pidfile"
  echo "$name started (PID $pid), logs: $logfile"
}

health_check() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    for i in $(seq 1 30); do
      if curl -fsS "$url" >/dev/null; then
        echo "Health OK: $url"
        return 0
      fi
      sleep 0.3
    done
    echo "Warning: backend health not confirmed at $url" >&2
  else
    echo "curl not available; skipping health check for $url"
  fi
}

open_browser() {
  local url="$1"
  [[ "$AUTO_OPEN_UI" == "1" ]] || return
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 &
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  elif command -v wslview >/dev/null 2>&1; then
    wslview "$url" >/dev/null 2>&1 &
  else
    echo "AUTO_OPEN_UI enabled but no opener found (open/xdg-open/wslview)." >&2
  fi
}

start_nginx_proxy() {
  if ! command -v nginx >/dev/null 2>&1; then
    echo "nginx binary not found; skipping proxy startup."
    return 1
  fi
  echo "Starting nginx reverse proxy (HTTPS port $HTTPS_PORT)..."
  if ! run_privileged nginx -t >/dev/null 2>&1; then
    echo "nginx -t failed. Check configuration before continuing." >&2
    return 1
  fi
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q nginx.service; then
    run_privileged systemctl enable --now nginx >/dev/null 2>&1 || true
    run_privileged systemctl reload nginx >/dev/null 2>&1 || run_privileged systemctl restart nginx >/dev/null 2>&1
  elif command -v service >/dev/null 2>&1 && [[ -x /etc/init.d/nginx ]]; then
    run_privileged service nginx reload >/dev/null 2>&1 || run_privileged service nginx start >/dev/null 2>&1
  elif command -v brew >/dev/null 2>&1 && brew services list >/dev/null 2>&1; then
    brew services start nginx >/dev/null 2>&1 || true
    brew services restart nginx >/dev/null 2>&1 || run_privileged nginx -s reload >/dev/null 2>&1 || run_privileged nginx >/dev/null 2>&1
  else
    run_privileged nginx -s reload >/dev/null 2>&1 || run_privileged nginx >/dev/null 2>&1
  fi
  if [[ -n "$PUBLIC_HTTPS_ORIGIN" ]]; then
    echo "nginx should now be serving $PUBLIC_HTTPS_ORIGIN (and https://localhost:$HTTPS_PORT)."
  else
    echo "nginx should now be serving https://localhost:$HTTPS_PORT (or your public domain)."
  fi
}

# Start backend
check_port_free "$BACKEND_PORT" "backend"
start_process backend env MEDIA_ROOT="$MEDIA_ROOT" uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
health_check "http://localhost:$BACKEND_PORT/healthz"

# Start UI (with reverse proxy compatible settings)
check_port_free "$UI_PORT" "ui"
start_process ui env MEDIA_ROOT="$MEDIA_ROOT" BACKEND_URL="$BACKEND_URL" streamlit run "$ROOT_DIR/ui/streamlit_app.py" \
  --server.port "$UI_PORT" \
  --server.address 0.0.0.0 \
  --server.enableCORS false \
  --server.enableXsrfProtection false

if [[ "$START_NGINX" == "1" ]]; then
  start_nginx_proxy || echo "Warning: unable to start nginx proxy."
else
  echo "Skipping nginx startup (set START_NGINX=1 to enable)."
fi

echo "\nServers started:"
echo "- Backend: http://localhost:$BACKEND_PORT (PID $(cat "$RUN_DIR/backend.pid"))"
echo "- UI:      http://localhost:$UI_PORT (PID $(cat "$RUN_DIR/ui.pid"))"
if [[ "$START_NGINX" == "1" ]]; then
  echo "- nginx:   https://localhost:$HTTPS_PORT"
  if [[ -n "$PUBLIC_HTTPS_ORIGIN" ]]; then
    echo "            $PUBLIC_HTTPS_ORIGIN"
  fi
fi
if [[ -n "$PUBLIC_HTTPS_ORIGIN" ]]; then
  echo "Public UI: $PUBLIC_HTTPS_ORIGIN"
fi

if [[ -n "$PUBLIC_HTTPS_ORIGIN" ]]; then
  open_browser "$PUBLIC_HTTPS_ORIGIN"
fi
open_browser "http://localhost:$UI_PORT"
