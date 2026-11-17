"""Recover only the stopped project app after a TIME_WAIT probe false alarm."""
import json
from pathlib import Path
import shlex
import socket
import subprocess
import time
import urllib.request
from backend import server

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    assert not any(r["status"] in {"running", "queued"} for r in server.all_objects("run"))
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", 8787))  # Refuse if any live listener owns the port.
    script = ROOT / "runtime/deployments/20261024/app-v22.sh"
    assert script.is_file() and " -u -m backend.server" in script.read_text()
    subprocess.run(["tmux", "new-session", "-d", "-s", "reading-bench-app", "-c", str(ROOT), "sh " + shlex.quote(str(script))], check=True)
    for attempt in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8787/api/health", timeout=3) as response:
                print(json.dumps({"health": json.load(response), "inference_calls": 0}))
            break
        except OSError:
            if attempt == 29:
                raise
            time.sleep(.5)
