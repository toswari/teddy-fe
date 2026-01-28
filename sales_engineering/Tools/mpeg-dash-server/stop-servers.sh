#!/usr/bin/env bash
# Stop FastAPI backend and Streamlit UI using tracked PIDs

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_process() {
  local name="$1"
  local pidfile="$RUN_DIR/$name.pid"
  if [[ ! -f "$pidfile" ]]; then
    echo "$name not running (no pidfile)."
    return 0
  fi
  local pid
  pid="$(cat "$pidfile")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$name not running (stale PID $pid). Removing pidfile."
    rm -f "$pidfile"
    return 0
  fi
  echo "Stopping $name (PID $pid) ..."
  kill -TERM "$pid" || true
  for i in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$name stopped."
      rm -f "$pidfile"
      return 0
    fi
    sleep 0.3
  done
  echo "Force killing $name (PID $pid) ..."
  kill -KILL "$pid" || true
  rm -f "$pidfile"
  echo "$name stopped forcibly."
}

stop_process ui
stop_process backend

echo "All servers stopped (if they were running)."
