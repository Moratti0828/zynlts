"""Allowlisted candidate corpus synchronization; no model, DB or service changes."""
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import urllib.request

EXTRA_FILES = {
    'data/annotation/development-selection-20261013.json',
    'docs/development-selection-20261013.md',
    'output/contamination-risk-audit-20261013.json',
    'docs/contamination-risk-audit-20261013.md',
}


def allowed(name):
    path = PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and '\\' not in name and
            str(path) == name and (name.startswith('data/candidates/') or name in EXTRA_FILES))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def api(path):
    with urllib.request.urlopen('http://127.0.0.1:8787' + path, timeout=60) as response:
        return json.load(response)


def safe_target(root, name):
    if not allowed(name):
        raise ValueError('Disallowed path: ' + name)
    path = root / name
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes project: ' + name)
    for part in (path, *path.parents):
        if part == root.parent:
            break
        if part.is_symlink():
            raise ValueError('Symlink path: ' + str(part))
    if path.exists() and not path.is_file():
        raise ValueError('Existing target is not a file: ' + name)
    return path


def pack(root, archive):
    root = root.resolve()
    names = set(EXTRA_FILES)
    for path in (root / 'data/candidates').rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in local corpus: ' + str(path))
        if path.is_file():
            names.add(path.relative_to(root).as_posix())
    names = sorted(names)
    files = {}
    for name in names:
        path = safe_target(root, name)
        data = path.read_bytes()
        files[name] = {'sha256': sha(data), 'bytes': len(data)}
    sys.path.insert(0, str(root))
    from backend.corpus_workspace import workspace_summary, workspace_article
    summary = workspace_summary(root)
    if summary['counts']['downloaded'] != 402 or summary['counts']['language'] != {'zh': 168, 'en': 234}:
        raise ValueError('Unexpected local corpus counts')
    examples = {}
    for lang in ('zh', 'en'):
        item = next(a for a in summary['articles'] if a['language'] == lang and a['body_available'])
        body = workspace_article(item['id'], root)
        examples[lang] = {'id': item['id'], 'text_sha256': sha(body['text'].encode('utf-8')),
            'declared_sha256': body['sha256'], 'raw_sha256': body.get('raw_sha256'),
            'characters': len(body['text'])}
    manifest = {'schema': 'reading-corpus-sync-v1', 'files': files,
        'local_counts': summary['counts'], 'local_annotation_counts': summary['annotation_counts'],
        'body_examples': examples}
    with tarfile.open(archive, 'w:gz') as tar:
        for name in names:
            tar.add(root / name, arcname=name, recursive=False)
        data = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode('utf-8')
        info = tarfile.TarInfo('corpus-sync-manifest.json')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    archive.with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(files), 'candidate_files': sum(n.startswith('data/candidates/') for n in files),
        'uncompressed_bytes': sum(f['bytes'] for f in files.values()), 'compressed_bytes': archive.stat().st_size,
        'archive_sha256': sha(archive.read_bytes()), 'local_counts': summary['counts'], 'body_examples': examples}))


def apply(archive, report_path):
    root = Path('/home/jmy/reading-bench')
    if root.resolve() != root or root.is_symlink():
        raise ValueError('Unexpected project root')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    before = api('/api/corpus-workspace')
    before_app = subprocess.check_output(['tmux', 'list-panes', '-t', 'reading-bench-app',
        '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    before_ollama = subprocess.check_output(['tmux', 'list-panes', '-t', 'reading-bench-ollama',
        '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if len(members) != len({m.name for m in members}) or any(not m.isfile() for m in members):
            raise ValueError('Duplicate, symlink, hardlink or non-file archive member')
        if len(members) > 5000 or sum(m.size for m in members) > 150_000_000:
            raise ValueError('Archive exceeds synchronization limit')
        manifest = json.load(tar.extractfile('corpus-sync-manifest.json'))
        if manifest.get('schema') != 'reading-corpus-sync-v1':
            raise ValueError('Invalid manifest schema')
        if set(manifest['files']) != {m.name for m in members if m.name != 'corpus-sync-manifest.json'}:
            raise ValueError('Manifest/archive member mismatch')
        payload = {}
        for member in members:
            if member.name == 'corpus-sync-manifest.json':
                continue
            target = safe_target(root, member.name)
            data = tar.extractfile(member).read()
            expected = manifest['files'][member.name]
            if len(data) != expected['bytes'] or sha(data) != expected['sha256']:
                raise ValueError('Payload hash/size mismatch: ' + member.name)
            payload[member.name] = (target, data)
    backup = Path(report['backup_path']) / ('corpus-sync-' + dt.datetime.now(dt.timezone.utc).strftime('%H%M%S'))
    if not backup.resolve().is_relative_to(root / 'runtime/deployments'):
        raise ValueError('Backup escapes project')
    backup.mkdir(parents=True, exist_ok=False)
    previous_files, missing_files = {}, []
    for name, (target, _) in payload.items():
        if target.exists():
            saved = backup / 'files' / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            previous_files[name] = sha(saved.read_bytes())
        else:
            missing_files.append(name)
    (backup / 'previous-files.json').write_text(json.dumps({'files_sha256': previous_files,
        'previous_missing_files': missing_files}, indent=2), encoding='utf-8')
    for name, (target, data) in payload.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if sha(target.read_bytes()) != manifest['files'][name]['sha256']:
            raise ValueError('Installed hash mismatch: ' + name)
    after = api('/api/corpus-workspace')
    examples = {}
    for lang, expected in manifest['body_examples'].items():
        body = api('/api/corpus-workspace/articles/' + expected['id'])
        actual = sha(body['text'].encode('utf-8'))
        if actual != expected['text_sha256'] or actual != body['sha256'] or not body.get('hash_verified'):
            raise ValueError('API body hash mismatch: ' + expected['id'])
        examples[lang] = {**expected, 'api_text_sha256': actual, 'hash_matches_local': True,
                          'api_hash_verified': body['hash_verified']}
    app_after = subprocess.check_output(['tmux', 'list-panes', '-t', 'reading-bench-app',
        '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    ollama_after = subprocess.check_output(['tmux', 'list-panes', '-t', 'reading-bench-ollama',
        '-F', '#{pane_pid}|#{pane_current_path}'], text=True).strip()
    counts = after['counts']
    annotation = after['annotation_counts']
    valid = (counts['downloaded'] == 402 and counts['total'] == 402 and
             counts['language'] == {'zh': 168, 'en': 234} and
             counts['states']['human_reviewed'] == 0 and counts['states']['frozen'] == 0 and
             all(annotation[k] == 0 for k in ('human_reviewed_articles', 'human_reviewed_questions',
                 'frozen_articles', 'frozen_questions')) and before_app == app_after and before_ollama == ollama_after)
    record = {'status': 'verified' if valid else 'verification_failed',
        'synced_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'backup_path': str(backup),
        'archive_sha256': sha(archive.read_bytes()), 'manifest': manifest,
        'counts_before': before['counts'], 'counts_after': counts,
        'annotation_counts_after': annotation, 'body_examples_verified': examples,
        'warnings_after': after['warnings'], 'overwritten_files_backed_up': len(previous_files),
        'new_files': len(missing_files), 'application_pane_before': before_app,
        'application_pane_after': app_after, 'ollama_pane_before': before_ollama,
        'ollama_pane_after': ollama_after, 'database_modified': False,
        'models_downloaded': False, 'model_inference_requested': False, 'services_restarted': False}
    report['corpus_sync'] = record
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if k != 'manifest'}))
    if not valid:
        raise ValueError('Corpus/API state verification failed; record saved for diagnosis')


parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['pack', 'apply'])
parser.add_argument('--root', type=Path)
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--report', type=Path)
args = parser.parse_args()
if args.mode == 'pack':
    pack(args.root, args.archive)
else:
    apply(args.archive, args.report)
