#!/usr/bin/env python3
"""Bounded read-only evidence precheck. Contract is supplied by the reviewer.

Never executes target code, follows URLs, loads hooks, or assigns grades.
A local contract is not automatically teacher approved. Hashes do not attest origin.
"""
import argparse
import hashlib
import json
from pathlib import Path

VERSION = 'evidence-review-v1'
LIMIT = 2 * 1024 * 1024


def read_json(path):
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('evidence exceeds 2 MiB limit')
    return raw, json.loads(raw)


def review(root, contract):
    root = Path(root).resolve()
    results = []
    for criterion in contract['criteria']:
        row = {'criterion_id': criterion['id'], 'status': 'INSUFFICIENT_EVIDENCE',
               'scope': criterion['scope'], 'evidence_ids': [], 'evidence_level': 'STATIC',
               'source': 'static_inspection', 'score_suggestion': None, 'human_signoff': 'pending',
               'finding': '', 'missing_evidence': [], 'suggested_check': 'Review the cited result and its provenance.'}
        if criterion.get('not_applicable'):
            if criterion['id'] in contract.get('approved_not_applicable', []) and contract.get('approval_reference'):
                row.update(status='NOT_APPLICABLE', finding='Exemption recorded in reviewer-supplied contract; approval authenticity requires human verification.')
            else:
                row['finding'] = 'No prior approval reference for exemption.'
            results.append(row)
            continue
        identity = criterion['evidence_id']
        item = contract.get('evidence', {}).get(identity)
        try:
            if item is None:
                raise ValueError('unknown evidence ID')
            if item.get('target_version') != contract['target_version']:
                raise ValueError('wrong target version')
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('path escape forbidden')
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError('symlink escape forbidden')
            raw, document = read_json(path)
            if hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('evidence hash mismatch')
            actual = document
            for key in criterion['field']:
                actual = actual[key]
            expected = criterion['equals']
            if type(actual) is not type(expected):
                raise ValueError('assertion value type mismatch')
            row.update(status='PASS' if actual == expected else 'FAIL', evidence_ids=[identity],
                       finding='Recorded field matches the fixed assertion.' if actual == expected else 'Recorded field contradicts the fixed assertion.',
                       observation={'field': criterion['field'], 'actual': actual, 'expected': expected},
                       declared_origin=item.get('declared_origin', 'unknown'))
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            row['finding'] = str(exc)
            row['missing_evidence'] = [identity]
            row['suggested_check'] = 'Supply a bounded same-version JSON result with a verified reference; do not infer execution from prose.'
        results.append(row)
    return {'reviewer_version': VERSION, 'target_version': contract['target_version'],
            'contract_status': contract.get('approval_status', 'unapproved_local_draft'),
            'execution': 'read_only_no_independent_rerun', 'results': results,
            'limits': 'Field checks do not establish origin, semantic support, security, personal ability or final grade.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw, contract = read_json(args.contract)
    result = review(args.root, contract)
    result['contract_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'states': [r['status'] for r in result['results']], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
