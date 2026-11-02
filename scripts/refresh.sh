#!/usr/bin/env bash
# Rebuild docs/data from nflverse. Usage: scripts/refresh.sh [season|latest]
set -euo pipefail
cd "$(dirname "$0")/.."
# Dependencies (run once):
#   pip install -r requirements.txt -r requirements-dev.txt
#   pip install --no-deps nfl_data_py==0.3.3
python -m nflrankings --season "${1:-latest}"
