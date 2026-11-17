from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.request

root = Path('/home/jmy/reading-bench')
parser = argparse.ArgumentParser()
parser.add_argument('--device', choices=['cpu', 'gpu'], default='cpu')
args = parser.parse_args()
corpus = json.loads((root / 'data/corpus.json').read_text(encoding='utf-8-sig'))
article = corpus['articles'][0]
question = article['questions'][0]
checks = []
for model in ['qwen2.5:7b-instruct', 'llama3.1:8b-instruct-q4_K_M']:
    payload = {'model': model, 'stream': False, 'format': 'json', 'keep_alive': '5m',
               'options': {'temperature': 0, 'seed': 42, 'num_ctx': 8192, 'num_predict': 180, 'num_thread': 2},
               'messages': [{'role': 'system', 'content': '只根据提供的文章回答问题。返回JSON对象，字段answer为答案，evidence为文章中支持答案的原文。'},
                            {'role': 'user', 'content': '文章：\n' + article['text'] + '\n\n问题：' + question['prompt']}]}
    start = time.monotonic()
    request = urllib.request.Request('http://127.0.0.1:11435/api/chat', data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=180) as response:
        receipt = json.load(response)
    with urllib.request.urlopen('http://127.0.0.1:11435/api/ps', timeout=10) as response:
        ps = json.load(response)
    check = {'model': model, 'recorded_at_server_utc': datetime.now(timezone.utc).isoformat(),
             'elapsed_seconds': round(time.monotonic() - start, 3), 'article_id': article['id'],
             'article_sha256': article['sha256'], 'question_id': question['id'], 'request': payload,
             'response': receipt, 'loaded_models': ps,
             'gpu_compute_processes': subprocess.run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory', '--format=csv'], capture_output=True, text=True, timeout=10).stdout.strip()}
    content = receipt.get('message', {}).get('content', '')
    if not receipt.get('done') or not content:
        raise SystemExit('Incomplete actual model call: ' + model)
    check['functional_call_ok'] = True
    try:
        parsed = json.loads(content)
        check['answer_matches_first_question'] = parsed.get('answer', '').strip() in question['answers']
    except (json.JSONDecodeError, TypeError, AttributeError):
        check['answer_matches_first_question'] = False
    if args.device == 'gpu' and not any(m.get('size_vram', 0) > 0 for m in ps.get('models', [])):
        raise SystemExit('Real call did not use GPU: ' + model)
    if args.device == 'cpu' and any(m.get('size_vram', 0) > 0 for m in ps.get('models', [])):
        raise SystemExit('Expected explicit CPU execution: ' + model)
    check['verified_execution_device'] = args.device
    checks.append(check)
    (root / 'runtime/server-model-smoke.json').write_text(json.dumps({'checks': checks}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'model': model, 'seconds': check['elapsed_seconds'], 'answer': content,
                      'loaded_models': ps, 'functional_call_ok': True, 'verified_device': args.device}, ensure_ascii=False), flush=True)
