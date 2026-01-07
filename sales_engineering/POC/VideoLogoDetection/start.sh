#!/usr/bin/env bash
set -euo pipefail
export FLASK_APP=run.py
export APP_ENV=${APP_ENV:-development}
python run.py
