#!/usr/bin/env bash
set -euo pipefail

# Launch the Streamlit app on the provided port or default to 8501
exec python -m streamlit run app.py --server.port "${PORT:-8501}" --server.address "${HOST:-0.0.0.0}"
