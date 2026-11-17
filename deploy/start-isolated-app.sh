#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
project_dir="$(pwd -P)"
if [[ -x "$project_dir/.venv/bin/python" ]]; then
  default_python="$project_dir/.venv/bin/python"
else
  default_python=/home/jmy/miniconda3/envs/torch_py311/bin/python
fi
python_bin="${READING_BENCH_PYTHON:-$default_python}"
if [[ ! -x "$python_bin" ]]; then python_bin="$(command -v python3)"; fi
mkdir -p runtime/app var
if tmux has-session -t reading-bench-app 2>/dev/null; then
  echo "Existing reading-bench-app session; inspect health/log before replacing it."
  exit 0
fi
printf -v launch 'exec env READING_BENCH_HOST=127.0.0.1 READING_BENCH_PORT=8787 READING_BENCH_OLLAMA_URL=http://127.0.0.1:11435 READING_BENCH_NUM_THREADS=2 READING_BENCH_DATA_DIR=%q %q -u -m backend.server >>%q 2>&1' "$project_dir/var" "$python_bin" "$project_dir/runtime/app/app.log"
tmux new-session -d -s reading-bench-app -c "$project_dir" "$launch"
echo "Started isolated loopback application in tmux reading-bench-app."
