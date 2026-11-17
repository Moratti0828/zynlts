"""Explicit one-paragraph CPU acceptance after full-passage timeout."""
import copy
import hashlib
import json
from pathlib import Path
import urllib.request

def api(path, data=None):
    request = urllib.request.Request('http://127.0.0.1:8787' + path,
        data=None if data is None else json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

project = Path('/home/jmy/reading-bench')
path = project / 'runtime/deployments/v2-20261013/report.json'
report = json.loads(path.read_text(encoding='utf-8'))
report['initial_full_passage_acceptance'] = copy.deepcopy(report['acceptance_run'])
report['initial_full_passage_note'] = 'The 1577-token full-passage request timed out at 180 seconds on two CPU threads; the failed run is retained.'
bank = json.loads((project / 'data/annotation/dev-pilot-v2.json').read_text(encoding='utf-8-sig'))
article = copy.deepcopy(bank['articles'][0])
article['paragraphs'] = article['paragraphs'][:1]
article['questions'] = [q for q in article['questions'] if q['id'] == 'q01']
article['presented_text_sha256'] = hashlib.sha256(article['paragraphs'][0]['text'].encode('utf-8')).hexdigest()
article['scope'] = 'excerpt'
article['scope_note'] = 'Explicit first-paragraph excerpt for engineering acceptance on CPU; not a formal benchmark article.'
article['annotation_state'] = 'ai_checked'
article['human_review_count'] = 0
bank['articles'] = [article]
bank['bank_version'] = 'server-engineering-single-paragraph-20261013'
bank['formal'] = False
bank['note'] = 'Explicit first-paragraph engineering excerpt; one AI draft question, zero human reviews; no model ranking.'
report['acceptance_bank_import'] = api('/api/v2/banks', {'id': bank['bank_version'], 'bank': bank})
request = copy.deepcopy(report['acceptance_request'])
request['bank_id'] = bank['bank_version']
report['acceptance_request'] = request
report['acceptance_run_created'] = api('/api/v2/runs', request)
report.pop('acceptance_run', None)
report.pop('acceptance_passed', None)
report['status'] = 'deployed_excerpt_acceptance_running'
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': report['status'], 'run_id': report['acceptance_run_created']['id'],
                  'presented_text_sha256': article['presented_text_sha256'], 'human_review_count': 0, 'formal': False}))
