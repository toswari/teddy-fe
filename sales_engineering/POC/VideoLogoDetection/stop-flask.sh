#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="tmp/runtime/pids/flask.pid"

if [[ -f "$PID_FILE" ]]; then
  FLASK_PID=$(cat "$PID_FILE")
  if kill -0 "$FLASK_PID" 2>/dev/null; then
    echo "[INFO] Stopping Flask server (PID $FLASK_PID)"
    kill "$FLASK_PID" 2>/dev/null || true
    # Give it a moment to shut down gracefully
    sleep 1
    # Force kill if still running
    if kill -0 "$FLASK_PID" 2>/dev/null; then
      kill -9 "$FLASK_PID" 2>/dev/null || true
    fi
    echo "[INFO] Flask server stopped."
  else
    echo "[WARN] No process found for Flask PID $FLASK_PID; removing stale PID file."
  fi
  rm -f "$PID_FILE"
else
  echo "[WARN] No Flask PID file found at $PID_FILE"
fi
