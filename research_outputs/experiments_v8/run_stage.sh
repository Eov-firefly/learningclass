#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export HF_HOME="${HF_HOME:-$PWD/.cache/huggingface}"
export TORCH_HOME="${TORCH_HOME:-$PWD/.cache/torch}"
JANUS_PYTHON="${JANUS_PYTHON:-$PWD/.venv/bin/python}"
JANUS_STAGE="${1:?Usage: bash run_stage.sh smoke|trace|quality|timing_pilot|timing [output-root]}"
JANUS_OUTPUT="${2:-runs}"
if [[ "$JANUS_STAGE" == timing ]]; then
  # Fresh Python/model process for each session; alternate model-session order.
  JANUS_SESSION_COUNT="$("$JANUS_PYTHON" -c 'import json; print(json.load(open("plan.json"))["stages"]["timing"]["sessions"])')"
  for ((JANUS_SESSION=0; JANUS_SESSION<JANUS_SESSION_COUNT; JANUS_SESSION++)); do
    if ((JANUS_SESSION % 2)); then JANUS_MODELS=(mistral qwen); else JANUS_MODELS=(qwen mistral); fi
    for JANUS_MODEL in "${JANUS_MODELS[@]}"; do
      "$JANUS_PYTHON" -u -m janus_v8.run --stage "$JANUS_STAGE" --model "$JANUS_MODEL" --session "$JANUS_SESSION" --out "$JANUS_OUTPUT"
    done
  done
else
  for JANUS_MODEL in qwen mistral; do
    "$JANUS_PYTHON" -u -m janus_v8.run --stage "$JANUS_STAGE" --model "$JANUS_MODEL" --out "$JANUS_OUTPUT"
  done
fi
