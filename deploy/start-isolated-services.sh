#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rb_project_dir="$(pwd -P)"
rb_device="${1:-cpu}"
[[ "$rb_device" == cpu || "$rb_device" =~ ^[0-9]+$ ]] || { echo 'Expected cpu or one physical GPU number' >&2; exit 2; }
mkdir -p runtime/logs

# Show the platform first; its model status updates when Ollama is available.
bash deploy/start-isolated-app.sh
if ! tmux has-session -t reading-bench-ollama 2>/dev/null; then
  if curl -fsS --max-time 2 http://127.0.0.1:11435/api/version >/dev/null 2>&1; then
    echo 'Port 11435 is already in use outside the expected session; inspect it before starting.' >&2
    exit 3
  fi
  printf -v rb_launch 'exec bash %q %q >>%q 2>&1' "$rb_project_dir/deploy/start-isolated-ollama.sh" "$rb_device" "$rb_project_dir/runtime/logs/ollama-current.log"
  tmux new-session -d -s reading-bench-ollama -c "$rb_project_dir" "$rb_launch"
else
  echo 'Existing reading-bench-ollama session retained.'
fi

for rb_url in http://127.0.0.1:8787/api/health http://127.0.0.1:11435/api/version; do
  rb_ready=false
  for rb_attempt in {1..40}; do
    if curl -fsS --max-time 1 "$rb_url" >/dev/null 2>&1; then rb_ready=true; break; fi
    sleep 0.25
  done
  if [[ "$rb_ready" != true ]]; then
    echo "Service unavailable: $rb_url; inspect runtime/app/app.log and runtime/logs/ollama-current.log." >&2
    exit 4
  fi
done
echo 'Platform and model service ready. Open the local SSH tunnel on port 8877.'
