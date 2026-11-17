#!/usr/bin/env python3
"""Allowlisted local rehearsals, calibration and in-memory known-bad mutations.

No model requests, target scripts, shell commands or production state are used.
"""
import argparse
from contextlib import nullcontext
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))


def execute(name, context):
    stream = io.StringIO()
    start = time.perf_counter()
    with context:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(name))
    return {'test': name, 'tests_run': result.testsRun, 'failures': len(result.failures),
            'errors': len(result.errors), 'skipped': len(result.skipped),
            'elapsed_s': time.perf_counter() - start, 'log': stream.getvalue()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='reading-defense-') as state:
        os.environ['READING_BENCH_DATA_DIR'] = state
        from backend import scoring, server, benchmark_v2, experiment_v2
        original_messages = experiment_v2.messages
        def leaking_messages(article, question, mode):
            return original_messages(article, question, mode) + [{'role': 'system', 'content': 'SECRET_GOLD'}]
        variants = [
            ('M1-sign-loss', 'test_contract.GraderContract.test_numeric_sign_and_percentage_are_not_lost',
             scoring, 'normalize', lambda value: ''),
            ('M2-always-full-F1', 'test_benchmark_v2.MetricV2Contract.test_overlap_f1_cannot_replace_strict_correctness_or_brier',
             benchmark_v2, 'short_token_f1', lambda *args: 1.0),
            ('M3-budget-bypass', 'test_contract.EvaluationContract.test_full_input_not_only_passage_is_bounded',
             server, 'validate_input_budget', lambda *args: None),
            ('M4-gold-leak', 'test_experiment_v2.ExperimentV2Contract.test_public_prompt_does_not_leak_gold_or_review_metadata',
             experiment_v2, 'messages', leaking_messages),
        ]
        mutations = []
        for identity, test, module, attribute, replacement in variants:
            good = execute(test, nullcontext())
            bad = execute(test, patch.object(module, attribute, replacement))
            restored = execute(test, nullcontext())
            mutations.append({'id': identity, 'baseline': good, 'known_bad': bad, 'restored': restored,
                              'detected': good['failures'] == good['errors'] == 0 and bad['failures'] > 0
                              and bad['errors'] == 0 and restored['failures'] == restored['errors'] == 0})
        rehearsals = [execute(name, nullcontext()) for name in [
            'test_evidence_reviewer.EvidenceReviewerContract',
            'test_experiment_v2.ExperimentV2Contract.test_cancel_and_resume_only_unfinished_keep_failure_denominator',
            'test_experiment_v2.ExperimentV2Contract.test_resume_rejects_changed_version_and_bank_snapshot',
            'test_experiment_v2.ExperimentV2Contract.test_unknown_inflight_attempt_survives_resume_and_new_result_is_linked',
            'test_live_demo.LiveDemoContract.test_concurrent_duplicate_posts_create_only_one_run',
        ]]
    report = {'schema': 'course-defense-rehearsal-v1', 'executed_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'execution': 'author_local_synthetic_rehearsal_not_peer_review_or_personal_exam',
              'model_calls': 0, 'mutations': mutations, 'rehearsals': rehearsals,
              'cost': {'human_minutes': None, 'ai_fee': None},
              'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for folder in ['backend', 'tests', 'scripts'] for p in (ROOT / folder).glob('*.py')}}
    report['status'] = 'PASS' if all(m['detected'] for m in mutations) and all(
        r['failures'] == r['errors'] == r['skipped'] == 0 for r in rehearsals) else 'FAIL'
    (args.output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'mutants_detected': sum(m['detected'] for m in mutations),
                      'calibration_and_recovery_tests': sum(r['tests_run'] for r in rehearsals)}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
