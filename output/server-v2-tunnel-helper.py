"""Restore only a loopback SSH forward; never stop existing processes."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

def health():
    with urllib.request.urlopen('http://127.0.0.1:8877/api/health', timeout=3) as response:
        value = json.load(response)
    with urllib.request.urlopen('http://127.0.0.1:8877/api/v2/banks/dev-pilot-v2', timeout=3) as response:
        bank = json.load(response)
    if value.get('version') != '1.2.0' or bank.get('id') != 'dev-pilot-v2':
        raise RuntimeError('Port is occupied by a different or outdated application')
    return value

parser = argparse.ArgumentParser()
parser.add_argument('--proxy', required=True)
parser.add_argument('--output', type=Path, required=True)
options = parser.parse_args()
occupied = False
with socket.socket() as probe:
    try:
        probe.bind(('127.0.0.1', 8877))
    except OSError:
        occupied = True
if occupied:
    result = {'status': 'reused_valid_project_tunnel', 'ssh_pid': None, 'health': health()}
else:
    command = ['ssh.exe', '-N', '-L', '127.0.0.1:8877:127.0.0.1:8787',
        '-o', options.proxy, '-o', 'BatchMode=yes', '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
        '-o', 'ConnectTimeout=8', 'gpu-server']
    logpath = options.output.with_suffix('.ssh.log')
    with logpath.open('ab') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(20):
        if process.poll() is not None:
            raise RuntimeError('SSH forward failed: ' + logpath.read_text(encoding='utf-8', errors='replace'))
        try:
            value = health()
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError('SSH forward health verification timed out; process retained for inspection')
    result = {'status': 'restored_loopback_forward', 'ssh_pid': process.pid,
              'health': value, 'ssh_log': str(logpath.resolve())}
result.update(url='http://127.0.0.1:8877/#v2experiment',
              bind='127.0.0.1:8877', destination='127.0.0.1:8787', host_alias='gpu-server')
options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result))
