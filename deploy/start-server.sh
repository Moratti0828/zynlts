#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-app}"
bash deploy/server-preflight.sh "$mode"
if [[ ! -f deploy/.env ]]; then python3 deploy/init_env.py; fi
compose=(docker compose --env-file deploy/.env -f deploy/compose.yml)
case "$mode" in
  app) ;;
  ollama-cpu) compose+=(--profile ollama) ;;
  ollama-gpu) compose+=(-f deploy/compose.gpu.yml --profile ollama) ;;
  *) echo "Usage: bash deploy/start-server.sh [app|ollama-cpu|ollama-gpu]" >&2; exit 2 ;;
esac
"${compose[@]}" config --quiet
"${compose[@]}" up -d --build
"${compose[@]}" ps
"${compose[@]}" exec -T app python -c "import time,urllib.request
for attempt in range(30):
    try:
        print(urllib.request.urlopen('http://127.0.0.1:8787/api/health',timeout=3).read().decode());break
    except Exception:
        if attempt == 29: raise
        time.sleep(1)"
echo "Application started. Model weights are not pulled by this script."
echo "Use an SSH tunnel to access the platform, then enter the token from deploy/.env."
