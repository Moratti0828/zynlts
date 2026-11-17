#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-ollama-cpu}"
compose=(docker compose --env-file deploy/.env -f deploy/compose.yml)
case "$mode" in
  ollama-cpu) compose+=(--profile ollama) ;;
  ollama-gpu) compose+=(-f deploy/compose.gpu.yml --profile ollama) ;;
  *) echo "Usage: bash deploy/pull-models.sh [ollama-cpu|ollama-gpu]" >&2; exit 2 ;;
esac
"${compose[@]}" config --quiet
"${compose[@]}" up -d ollama
ready=0
for attempt in {1..30}; do
  if "${compose[@]}" exec -T ollama ollama list >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [[ "$ready" != "1" ]]; then echo "Ollama did not become ready in 30 seconds." >&2; exit 1; fi
"${compose[@]}" exec -T ollama ollama pull qwen2.5:7b-instruct
"${compose[@]}" exec -T ollama ollama pull llama3.1:8b-instruct-q4_K_M
python3 deploy/capture-models.py --url http://127.0.0.1:11434 --output deploy/model-manifest.json
echo "Models pulled and recorded. Verify digests and provenance before a formal benchmark."
