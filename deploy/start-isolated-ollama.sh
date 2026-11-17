#!/usr/bin/env bash
set -euo pipefail
rb_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
gpu="${1:-cpu}"
if [[ "$gpu" == cpu ]]; then
  device=-1
else
  [[ "$gpu" =~ ^[0-9]+$ ]] || { echo 'Expected cpu or one physical GPU number' >&2; exit 2; }
  free_mib=$(nvidia-smi --id="$gpu" --query-gpu=memory.free --format=csv,noheader,nounits | tr -d ' ')
  [[ "$free_mib" =~ ^[0-9]+$ ]] && (( free_mib >= 18432 )) || { echo 'Selected GPU has less than 18GiB free' >&2; exit 3; }
  uuid=$(nvidia-smi --id="$gpu" --query-gpu=uuid --format=csv,noheader)
  if nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader | grep -Fxq "$uuid"; then
    echo 'Selected GPU already has a compute process; do not use it' >&2
    exit 4
  fi
  device="$gpu"
  export CUDA_VISIBLE_DEVICES="$device"
  python3 "$rb_script_dir/cuda-readiness.py" --device "$device" --output /home/jmy/reading-bench/runtime/gpu-readiness.json
fi
export CUDA_VISIBLE_DEVICES="$device"
export OLLAMA_HOST=127.0.0.1:11435
export OLLAMA_MODELS=/home/jmy/reading-bench/runtime/models
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_NUM_PARALLEL=1
exec /usr/local/bin/ollama serve
