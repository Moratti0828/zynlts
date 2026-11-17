#!/usr/bin/env python3
"""Offline same-input comparison. Never calls a model or overwrites evidence."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.benchmark_v2 import short_token_f1 as candidate
from scripts.baselines.short_f1_v1 import short_token_f1 as baseline


def fixtures():
    cases = []
    for lang, phrase in [('en', 'red red blue not green '), ('zh', '甲乙甲 AI 不支持 ' )]:
        for length in (1, 8, 32):
            for count in (1, 4, 16):
                prediction = phrase * length
                cases.append({'language': lang, 'prediction': prediction,
                              'aliases': [phrase * (i % length + 1) for i in range(count)]})
        cases.extend({'language': lang, 'prediction': p, 'aliases': a}
                     for p, a in [('', ['']), ('!!!', ['???']), ('甲 AI', []), ('ＡＩ', ['AI'])])
    return cases


def score_all(fn, cases):
    return [fn(c['prediction'], c['aliases'], c['language']) for c in cases]


def known_cases(fn):
    return (fn('red red red blue', ['red blue'], 'en') == 2 / 3
            and fn('!!!', ['???'], 'en') == 0
            and fn('甲乙', ['甲'], 'zh') == 2 / 3
            and fn('red', ['blue'], 'en') == 0
            and fn('ＡＩ', ['AI'], 'en') == 1)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    cases = fixtures()
    report = {'schema': 'reading-engineering-experiment-v1',
              'experiment': 'EXP-001', 'executed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'execution': 'local_offline_microbenchmark_not_model_inference',
              'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                              'machine': platform.machine()},
              'rounds_planned': 3, 'passes_per_round': 20, 'inputs': cases, 'runs': [],
              'cost': {'model_calls': 0, 'human_minutes': None, 'ai_development_cost': None,
                       'memory_bytes': None, 'maintenance_cost': None},
              'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                for path in ['backend/benchmark_v2.py', 'scripts/baselines/short_f1_v1.py',
                                             'scripts/compare_short_f1.py', 'docs/experiments/EXP-001-protocol.md']}}
    checks = {name: known_cases(fn) for name, fn in [('baseline', baseline), ('candidate', candidate)]}
    report['known_cases'] = checks
    for round_id in range(1, 4):
        order = [('baseline', baseline), ('candidate', candidate)]
        if round_id % 2 == 0:
            order.reverse()
        for name, fn in order:
            record = {'round': round_id, 'variant': name, 'output': None, 'error': None}
            start = time.perf_counter()
            try:
                record['output'] = [score_all(fn, cases) for _ in range(20)]
            except Exception as exc:
                record['error'] = type(exc).__name__ + ': ' + str(exc)
            record['elapsed_s'] = time.perf_counter() - start
            report['runs'].append(record)
    all_good = all(checks.values()) and all(r['error'] is None for r in report['runs'])
    report['outputs_identical'] = all_good and all(r['output'] == report['runs'][0]['output'] for r in report['runs'])
    report['median_s'] = {name: statistics.median(r['elapsed_s'] for r in report['runs'] if r['variant'] == name)
                          for name in ['baseline', 'candidate']}
    report['status'] = 'PASS' if report['outputs_identical'] else 'FAIL'
    report['decision'] = ('limited_adoption' if report['median_s']['candidate'] < report['median_s']['baseline']
                          else 'retain_baseline_or_investigate') if report['status'] == 'PASS' else 'reject_candidate'
    (args.output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['status', 'outputs_identical', 'median_s', 'decision']}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
