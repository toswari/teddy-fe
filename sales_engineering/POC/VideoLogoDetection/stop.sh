#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/tmp/runtime/pids/flask.pid"

echo "[INFO] Stopping Flask server..."

# Kill by PID file
if [[ -f "$PID_FILE" ]]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "[INFO] Killing Flask process (PID: $PID)"
    kill "$PID" 2>/dev/null || kill -9 "$PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "[INFO] Flask server stopped."
  else
    echo "[WARN] No process found for Flask PID $PID; removing stale PID file."
    rm -f "$PID_FILE"
  fi
else
  echo "[WARN] PID file not found at $PID_FILE"
fi

# Fallback: Kill by port
if lsof -ti:4000 >/dev/null 2>&1; then
  echo "[INFO] Killing process on port 4000..."
  lsof -ti:4000 | xargs kill -9 2>/dev/null || true
  echo "[INFO] Port 4000 freed."
fi

echo "[INFO] Cleanup complete."
