#!/usr/bin/env python3
"""Run offline course checks in isolated state and retain actual logs/costs."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ required')
    for module in ['tokenizers', 'jinja2']:
        __import__(module)  # Fail explicitly instead of silently skipping exact-budget coverage.
    if not shutil.which('node'):
        parser.error('Node.js is required for frontend checks')
    args.output.mkdir(parents=True, exist_ok=False)
    checks = [
        ('python-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('demo-frontend', ['node', 'tests/test_live_demo_frontend.js']),
        ('reference-frontend', ['node', 'tests/test_public_reference_frontend.js']),
        ('history-integrity', [sys.executable, 'scripts/verify_expansion_delivery_20261025.py']),
        ('defense-drill', [sys.executable, 'scripts/course_defense_drill.py', '--output', str(args.output.resolve() / 'defense-drill')]),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='reading-course-') as state:
        env = dict(os.environ, READING_BENCH_DATA_DIR=state)
        for name, command in checks:
            start = time.perf_counter()
            try:
                result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
                output, code = result.stdout + result.stderr, result.returncode
            except subprocess.TimeoutExpired as exc:
                output, code = str(exc), 124
            elapsed = time.perf_counter() - start
            log = args.output / (name + '.log')
            log.write_text(output, encoding='utf-8')
            rows.append({'name': name, 'command': ['python' if c == sys.executable else c for c in command],
                         'exit_code': code, 'elapsed_s': elapsed, 'log': log.name,
                         'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()})
    paths = sorted({p for directory in ['backend', 'scripts', 'tests', 'frontend']
                    for p in (ROOT / directory).rglob('*')
                    if p.is_file() and '__pycache__' not in p.parts})
    report = {'executed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'status': 'PASS' if all(r['exit_code'] == 0 for r in rows) else 'FAIL',
              'checks': rows, 'model_calls': 0, 'scope': 'offline tests and archived evidence integrity; no new model inference',
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    (args.output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': rows}, ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
