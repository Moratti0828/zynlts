"""Synchronize the two final explanatory changes, preserving deployment history."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

FILES = ('docs/later-adjustment-plan-20261013.md', 'data/benchmark-spec-v2.json')
parser = argparse.ArgumentParser()
parser.add_argument('--proxy', required=True)
args = parser.parse_args()
project = Path.cwd()
expected = {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in FILES}
ssh = ['ssh.exe', '-o', args.proxy, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', 'gpu-server']
staging = '/home/jmy/reading-bench/runtime/deployments/v2-20261013/final-metadata'
subprocess.run(ssh + ['mkdir -p ' + staging], check=True)
for name in FILES:
    subprocess.run(['scp.exe', '-o', args.proxy, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
        str(project / name), 'gpu-server:' + staging + '/' + Path(name).name], check=True)
remote_code = '''
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
root = Path('/home/jmy/reading-bench')
if root.resolve() != root or root.is_symlink():
    raise ValueError('Unexpected project root')
expected = EXPECTED_HASHES
report_path = root / 'runtime/deployments/v2-20261013/report.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
backup = Path(report['backup_path']) / 'final-metadata-sync'
if not backup.resolve().is_relative_to(root / 'runtime/deployments'):
    raise ValueError('Backup escapes project')
record = {'files_sha256': expected, 'backup_path': str(backup), 'previous_missing_files': [],
          'synced_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
for name, digest in expected.items():
    target = root / name
    if not target.resolve().is_relative_to(root):
        raise ValueError('Target escapes project')
    for part in (target, *target.parents):
        if part == root.parent:
            break
        if part.is_symlink():
            raise ValueError('Symlink target')
    staged = root / 'runtime/deployments/v2-20261013/final-metadata' / Path(name).name
    data = staged.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Staged hash mismatch: ' + name)
    saved = backup / name
    if target.exists():
        saved.parent.mkdir(parents=True, exist_ok=True)
        if saved.exists():
            raise ValueError('Backup already exists: ' + name)
        shutil.copy2(target, saved)
    else:
        record['previous_missing_files'].append(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError('Installed hash mismatch: ' + name)
report['final_metadata_sync'] = record
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record))
'''.replace('EXPECTED_HASHES', repr(expected))
completed = subprocess.run(ssh + ['cd /home/jmy/reading-bench && .venv/bin/python -'],
    input=remote_code.encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
record = json.loads(completed.stdout.decode('utf-8'))
if record['files_sha256'] != expected:
    raise ValueError('Unexpected remote hashes')
report_path = project / 'output/server-v2-deployment-20261013.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
report['final_metadata_sync'] = record
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record))
