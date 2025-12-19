#!/usr/bin/env bash
set -euo pipefail

# Stop any running Streamlit app instances tied to this project
if pkill -f "streamlit run app.py"; then
  echo "Stopped Streamlit app session."
else
  echo "No matching Streamlit app processes found."
fi
