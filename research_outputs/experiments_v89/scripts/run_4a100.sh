#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m janus_min.launch --output "${1:-runs/minimal}" --devices "${2:-0,1,2,3}" --local-files-only
