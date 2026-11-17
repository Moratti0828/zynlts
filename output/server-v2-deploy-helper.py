"""Small-file, allowlisted deployment and acceptance for this project's server."""
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import tarfile
import time
import urllib.request

PROJECT = Path('/home/jmy/reading-bench')
ALLOWED_PREFIXES = ('backend/', 'frontend/', 'deploy/', 'scripts/')
ALLOWED_FILES = {
    'requirements-tokenizer.txt', 'data/annotation/dev-pilot-v2.json',
    'data/benchmark-spec-v2.json',
    'runtime/tokenizers/qwen25-7b-a09a354/manifest.json',
    'runtime/tokenizers/qwen25-7b-a09a354/tokenizer.json',
    'runtime/tokenizers/qwen25-7b-a09a354/tokenizer_config.json',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def permitted(name):
    value = PurePosixPath(name)
    return (not value.is_absolute() and '..' not in value.parts and
            '\\' not in name and name == str(value) and
            (name in ALLOWED_FILES or
             (name.startswith(ALLOWED_PREFIXES) and '__pycache__' not in value.parts and
              value.suffix != '.pyc')))


def api(path, data=None):
    request = urllib.request.Request('http://127.0.0.1:8787' + path,
        data=None if data is None else json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def pack(root, archive):
    root = root.resolve()
    names = set(ALLOWED_FILES)
    for folder in ('backend', 'frontend', 'deploy', 'scripts'):
        names.update(str(p.relative_to(root)).replace('\\', '/')
                     for p in (root / folder).rglob('*') if p.is_file())
    names = sorted(n for n in names if permitted(n))
    files = {n: {'sha256': sha((root / n).read_bytes()), 'bytes': (root / n).stat().st_size}
             for n in names}
    manifest = {'schema': 'reading-bench-v2-deployment-1', 'files': files}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'w:gz') as tar:
        for n in names:
            tar.add(root / n, arcname=n, recursive=False)
        data = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode('utf-8')
        info = tarfile.TarInfo('deployment-manifest.json')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    archive.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'archive_sha256': sha(archive.read_bytes()),
                      'files': len(files), 'bytes': sum(x['bytes'] for x in files.values())}))


def checked_target(name):
    if not permitted(name):
        raise ValueError('Disallowed path: ' + name)
    target = PROJECT / name
    if not target.resolve().is_relative_to(PROJECT):
        raise ValueError('Path escapes project: ' + name)
    for part in (target, *target.parents):
        if part == PROJECT.parent:
            break
        if part.is_symlink():
            raise ValueError('Symlink target: ' + str(part))
    return target


def deploy(archive, report_path):
    if PROJECT.resolve() != PROJECT or PROJECT.is_symlink():
        raise ValueError('Unexpected project root')
    report = {'project': str(PROJECT), 'archive_sha256': sha(archive.read_bytes()),
              'status': 'preparing', 'models_downloaded': False,
              'hardware_note': 'GPU 0 cuInit returned CUDA_ERROR_UNKNOWN; existing CPU Ollama retained.'}
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if len({m.name for m in members}) != len(members):
            raise ValueError('Duplicate archive members')
        if any(not m.isfile() for m in members) or sum(m.size for m in members) > 100_000_000:
            raise ValueError('Non-file or excessive archive member')
        manifest_member = next(m for m in members if m.name == 'deployment-manifest.json')
        manifest = json.load(tar.extractfile(manifest_member))
        if manifest.get('schema') != 'reading-bench-v2-deployment-1':
            raise ValueError('Unknown manifest schema')
        if set(manifest['files']) != {m.name for m in members if m.name != 'deployment-manifest.json'}:
            raise ValueError('Manifest/member mismatch')
        payload = {}
        for m in members:
            if m.name == 'deployment-manifest.json':
                continue
            target = checked_target(m.name)
            if m.size != manifest['files'][m.name]['bytes']:
                raise ValueError('Size mismatch: ' + m.name)
            data = tar.extractfile(m).read()
            if sha(data) != manifest['files'][m.name]['sha256']:
                raise ValueError('Hash mismatch: ' + m.name)
            payload[m.name] = (target, data, m.mode)
    report['manifest'] = manifest
    report['health_before'] = api('/api/health')
    report['runs_before'] = api('/api/runs')
    if any(r['status'] in {'queued', 'running'} for r in report['runs_before']['runs']):
        raise ValueError('Active application run; deployment aborted')
    pane = subprocess.check_output(['tmux', 'list-panes', '-t', 'reading-bench-app',
        '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    pane_pid, pane_cwd = pane.split('|')
    if pane_cwd != str(PROJECT):
        raise ValueError('App session is not this project')
    command = Path('/proc/' + pane_pid + '/cmdline').read_bytes().replace(b'\0', b' ').decode()
    if '-m backend.server' not in command:
        raise ValueError('App process is not the known project backend')
    report['old_app_pid'] = int(pane_pid)
    timestamp = time.strftime('%Y%m%d-%H%M%S', time.gmtime())
    backup = PROJECT / 'runtime' / 'deployments' / ('v2-backup-' + timestamp)
    backup.mkdir(parents=True, exist_ok=False)
    report['backup_path'] = str(backup)
    report['previous_missing_files'] = []
    for name, (target, _, _) in payload.items():
        if target.exists():
            destination = backup / 'files' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)
        else:
            report['previous_missing_files'].append(name)
    db = PROJECT / 'var' / 'bench.sqlite3'
    if db.exists():
        with sqlite3.connect('file:' + str(db) + '?mode=ro', uri=True) as original:
            with sqlite3.connect(backup / 'bench.sqlite3') as saved:
                original.backup(saved)
        report['database_backup'] = str(backup / 'bench.sqlite3')
    (backup / 'deployment-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    subprocess.run(['tmux', 'kill-session', '-t', 'reading-bench-app'], check=True)
    try:
        for name, (target, data, mode) in payload.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode & 0o777)
            if sha(target.read_bytes()) != manifest['files'][name]['sha256']:
                raise ValueError('Installed hash mismatch: ' + name)
        subprocess.run(['bash', str(PROJECT / 'deploy/start-isolated-app.sh')], check=True)
        for _ in range(20):
            try:
                report['health_after'] = api('/api/health')
                if report['health_after'].get('version') == '1.2.0':
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError('New application health check failed')
    except Exception:
        subprocess.run(['tmux', 'kill-session', '-t', 'reading-bench-app'], check=False)
        for name in payload:
            target = checked_target(name)
            saved = backup / 'files' / name
            if saved.exists():
                shutil.copy2(saved, target)
            elif target.exists():
                target.unlink()
        subprocess.run(['bash', str(PROJECT / 'deploy/start-isolated-app.sh')], check=True)
        report['status'] = 'rolled_back'
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise
    report['banks'] = api('/api/v2/banks')
    report['models'] = api('/api/models')
    versions = subprocess.check_output([str(PROJECT / '.venv/bin/python'), '-c',
        'import tokenizers,jinja2,json;print(json.dumps({"tokenizers":tokenizers.__version__,"Jinja2":jinja2.__version__}))'], text=True)
    report['dependency_versions'] = json.loads(versions)
    request = {'bank_id': 'dev-pilot-v2', 'model_ids': ['qwen25-7b'],
        'article_ids': ['zh-nbs-02a36a9fc6f8-devpilot'], 'question_ids': ['q01'],
        'allow_draft': True, 'strict_time': True, 'strict_budget': True,
        'max_tokens': 512, 'temperature': 0, 'bootstrap_repetitions': 0,
        'question_limit': 1, 'mode': 'with_context'}
    report['acceptance_request'] = request
    created = api('/api/v2/runs', request)
    report['acceptance_run_created'] = created
    report['status'] = 'deployed_acceptance_running'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'backup_path': str(backup), 'run_id': created['id']}))


def finalize(report_path):
    report = json.loads(report_path.read_text(encoding='utf-8'))
    run = api('/api/v2/runs/' + report['acceptance_run_created']['id'])
    report['acceptance_run'] = run
    if run['status'] not in {'completed', 'failed', 'cancelled', 'interrupted'}:
        print(json.dumps({'status': run['status'], 'progress': run['progress']}))
        return
    rows = run['results']
    report['acceptance_passed'] = (run['status'] == 'completed' and len(rows) == 1 and
        not rows[0].get('error') and rows[0].get('budget', {}).get('runtime_count_matches') is True)
    report['status'] = 'deployed_acceptance_passed' if report['acceptance_passed'] else 'deployed_acceptance_failed'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'run_id': run['id'], 'progress': run['progress'],
                      'row_error': rows[0].get('error') if rows else None,
                      'token_budget': rows[0].get('budget') if rows else None}))


def record_runtime(report_path):
    report = json.loads(report_path.read_text(encoding='utf-8'))
    with urllib.request.urlopen('http://127.0.0.1:11435/api/ps', timeout=10) as response:
        report['ollama_runtime_ps'] = json.load(response)
    report['runtime_snapshot_at_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    report['application_pane'] = subprocess.check_output(['tmux', 'list-panes', '-t',
        'reading-bench-app', '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    report['ollama_pane'] = subprocess.check_output(['tmux', 'list-panes', '-t',
        'reading-bench-ollama', '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    report['health_current'] = api('/api/health')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ollama_runtime_ps': report['ollama_runtime_ps'],
                      'application_pane': report['application_pane'],
                      'ollama_pane': report['ollama_pane']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['pack', 'deploy', 'finalize', 'record-runtime'])
    parser.add_argument('--root', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--report', type=Path)
    options = parser.parse_args()
    if options.mode == 'pack':
        pack(options.root, options.archive)
    elif options.mode == 'deploy':
        deploy(options.archive, options.report)
    elif options.mode == 'finalize':
        finalize(options.report)
    else:
        record_runtime(options.report)
