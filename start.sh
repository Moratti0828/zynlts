#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ -n "${READING_BENCH_PYTHON:-}" ]; then
    exec "$READING_BENCH_PYTHON" -m backend.server
fi
for candidate in .venv/bin/python python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3,11))' 2>/dev/null; then
        exec "$candidate" -m backend.server
    fi
done
printf '%s\n' 'Reading Bench requires Python 3.11+. Install it or set READING_BENCH_PYTHON.' >&2
exit 1
