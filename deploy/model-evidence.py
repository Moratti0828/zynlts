import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path('/home/jmy/reading-bench/runtime')
EXPECTED = {
    'qwen2.5:7b-instruct': '845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e',
    'llama3.1:8b-instruct-q4_K_M': '46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e',
}

def fetch(url, payload=None):
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)

def command(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=30).stdout.strip()

record = {
    'recorded_at_server_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'host': command(['hostname']),
    'addresses': command(['hostname', '-I']),
    'user': command(['id', '-un']),
    'gpu': command(['nvidia-smi', '--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu', '--format=csv']),
    'gpu_compute_processes': command(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory', '--format=csv']),
    'ollama_version': fetch('http://127.0.0.1:11435/api/version'),
    'tags': fetch('http://127.0.0.1:11435/api/tags'),
    'loaded_models': fetch('http://127.0.0.1:11435/api/ps'),
    'models': [],
}
record['ollama_service_environment'] = []
for pid in command(['pgrep', '-u', 'jmy', '-x', 'ollama']).splitlines():
    process_dir = Path('/proc') / pid
    try:
        arguments = process_dir.joinpath('cmdline').read_bytes().decode().split('\0')
        if 'serve' not in arguments:
            continue
        environment = dict(item.split('=', 1) for item in process_dir.joinpath('environ').read_bytes().decode().split('\0') if '=' in item)
        keys = ['CUDA_VISIBLE_DEVICES', 'OLLAMA_HOST', 'OLLAMA_MODELS', 'OLLAMA_MAX_LOADED_MODELS', 'OLLAMA_NUM_PARALLEL']
        record['ollama_service_environment'].append({'pid': int(pid), 'command': arguments, 'environment': {key: environment.get(key) for key in keys}})
    except (OSError, UnicodeError):
        continue
tags = {m['name']: m for m in record['tags'].get('models', [])}
for name, expected in EXPECTED.items():
    if name not in tags:
        continue
    entry = tags[name]
    if entry['digest'] != expected:
        raise SystemExit('Wrong model digest: ' + name)
    family, tag = name.split(':', 1)
    manifest_path = ROOT / 'models/manifests/registry.ollama.ai/library' / family / tag
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected:
        raise SystemExit('Local manifest does not match digest: ' + name)
    show = fetch('http://127.0.0.1:11435/api/show', {'model': name})
    manifest = json.loads(manifest_bytes)
    blobs = []
    for blob in [manifest['config']] + manifest['layers']:
        blob_path = ROOT / 'models/blobs' / blob['digest'].replace(':', '-')
        checksum = hashlib.sha256()
        with blob_path.open('rb') as input_file:
            for chunk in iter(lambda: input_file.read(8 * 1024 * 1024), b''):
                checksum.update(chunk)
        actual_hash = checksum.hexdigest()
        if actual_hash != blob['digest'].split(':', 1)[1] or blob_path.stat().st_size != blob['size']:
            raise SystemExit('Blob checksum/size mismatch: ' + str(blob_path))
        blobs.append({'digest': blob['digest'], 'size': blob['size'], 'sha256_verified': True})
    record['models'].append({'name': name, 'digest': expected, 'manifest': manifest,
                             'manifest_sha256_verified': True, 'blobs_verified': blobs, 'show_metadata': show})
output = ROOT / 'server-model-evidence.json'
output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'output': str(output), 'host': record['host'], 'models_verified': len(record['models']),
                  'loaded_models': record['loaded_models']}, ensure_ascii=False))
