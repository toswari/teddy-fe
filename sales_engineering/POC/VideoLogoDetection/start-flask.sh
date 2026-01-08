#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="tmp/runtime/pids/flask.pid"
LOG_FILE="tmp/logs/flask.log"

# Stop any existing Flask process first
if [[ -f "$PID_FILE" ]]; then
  EXISTING_PID=$(cat "$PID_FILE")
  if kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "[INFO] Stopping existing Flask server (PID $EXISTING_PID)"
    pkill -TERM -P "$EXISTING_PID" 2>/dev/null || true
    kill "$EXISTING_PID" 2>/dev/null || true
    for _ in {1..5}; do
      if ! kill -0 "$EXISTING_PID" 2>/dev/null; then
        break
      fi
      sleep 0.5
    done
    if kill -0 "$EXISTING_PID" 2>/dev/null; then
      pkill -KILL -P "$EXISTING_PID" 2>/dev/null || true
      kill -9 "$EXISTING_PID" 2>/dev/null || true
    fi
  fi
  rm -f "$PID_FILE"
fi

echo "[INFO] Loading environment from .env"
set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a

echo "[INFO] Starting Flask development server"
mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"

nohup ./start.sh > "$LOG_FILE" 2>&1 &
FLASK_PID=$!
echo "$FLASK_PID" > "$PID_FILE"

echo "[INFO] Flask server launched with PID $FLASK_PID. Logs: $LOG_FILE"
echo "[INFO] Open http://localhost:4000/ in your browser to use the dashboard."
echo "[INFO] Tailing Flask logs (Ctrl+C to stop tailing only):"

tail -f "$LOG_FILE"
