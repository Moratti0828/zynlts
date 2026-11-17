"""Backup and synchronize three authorized project documents only."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

FILES = ('README.md', 'docs/benchmark-protocol-v2.md', 'docs/platform-v2-execution-20261013.md')

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['pack', 'apply'])
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--report', type=Path)
args = parser.parse_args()
root = args.root.resolve()
if args.mode == 'pack':
    manifest = {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in FILES}
    with tarfile.open(args.archive, 'w:gz') as tar:
        for name in FILES:
            tar.add(root / name, arcname=name, recursive=False)
        data = json.dumps(manifest).encode('utf-8')
        info = tarfile.TarInfo('document-manifest.json')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    print(json.dumps(manifest))
else:
    if root != Path('/home/jmy/reading-bench'):
        raise ValueError('Unexpected project root')
    report = json.loads(args.report.read_text(encoding='utf-8'))
    backup = Path(report['backup_path']) / 'docs-sync'
    if not backup.resolve().is_relative_to(root / 'runtime/deployments'):
        raise ValueError('Invalid backup path')
    with tarfile.open(args.archive, 'r:gz') as tar:
        members = tar.getmembers()
        if {m.name for m in members} != set(FILES) | {'document-manifest.json'} or len(members) != 4:
            raise ValueError('Unexpected archive member')
        if any(not m.isfile() for m in members):
            raise ValueError('Non-file archive member')
        manifest = json.load(tar.extractfile('document-manifest.json'))
        for name in FILES:
            target = root / name
            if not target.resolve().is_relative_to(root):
                raise ValueError('Document target escapes project')
            for part in (target, *target.parents):
                if part == root.parent:
                    break
                if part.is_symlink():
                    raise ValueError('Symlink in document target')
            data = tar.extractfile(name).read()
            if hashlib.sha256(data).hexdigest() != manifest[name]:
                raise ValueError('Document hash mismatch')
            saved = backup / name
            if target.exists() and not saved.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if hashlib.sha256(target.read_bytes()).hexdigest() != manifest[name]:
                raise ValueError('Installed document hash mismatch')
    report['document_sync'] = {'files_sha256': manifest, 'backup_path': str(backup)}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['document_sync']))
