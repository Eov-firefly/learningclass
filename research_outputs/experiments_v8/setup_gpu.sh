#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export HF_HOME="${HF_HOME:-$PWD/.cache/huggingface}"
export TORCH_HOME="${TORCH_HOME:-$PWD/.cache/torch}"
JANUS_BOOTSTRAP_PYTHON="${JANUS_BOOTSTRAP_PYTHON:-python3}"
"$JANUS_BOOTSTRAP_PYTHON" -c 'import sys; assert (3,10) <= sys.version_info[:2] < (3,13), "Use Python 3.10–3.12 (3.11 recommended) for this pinned environment"'
"$JANUS_BOOTSTRAP_PYTHON" -m venv .venv
.venv/bin/python -m pip install 'torch==2.6.0' --index-url https://download.pytorch.org/whl/cu124
.venv/bin/python -m pip install -r requirements-gpu.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -c 'import torch; assert torch.cuda.is_available(), "CUDA GPU not available"; assert torch.cuda.is_bf16_supported(), "BF16 required"; print(torch.__version__, torch.cuda.get_device_name(0))'
