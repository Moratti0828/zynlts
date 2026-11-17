#!/usr/bin/env bash
set -euo pipefail
mode="${1:-app}"
case "$mode" in app|ollama-cpu|ollama-gpu) ;; *) echo "Usage: bash deploy/server-preflight.sh [app|ollama-cpu|ollama-gpu]" >&2; exit 2 ;; esac
command -v python3 >/dev/null || { echo "python3 is required for setup." >&2; exit 1; }
command -v docker >/dev/null || { echo "Install Docker Engine and Compose before starting." >&2; exit 1; }
python3 --version
docker compose version
docker info --format '{{.ServerVersion}}'
uname -srmo
df -h .
if command -v free >/dev/null; then free -h; fi
if command -v nvidia-smi >/dev/null; then nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv; fi
if [[ "$mode" == "ollama-gpu" ]]; then
  command -v nvidia-smi >/dev/null || { echo "NVIDIA driver/nvidia-smi is required for ollama-gpu." >&2; exit 1; }
  nvidia-smi >/dev/null
  command -v nvidia-ctk >/dev/null || { echo "Install NVIDIA Container Toolkit for Docker GPU access." >&2; exit 1; }
fi
echo "Preflight complete. This does not benchmark memory, model latency, or GPU container access."
