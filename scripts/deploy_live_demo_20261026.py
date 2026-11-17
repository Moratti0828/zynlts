"""Deploy staged demo files on the idle project server; never touch model jobs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "runtime/deployments/20261026"
FILES = ("backend/server.py", "backend/live_demo.py", "frontend/index.html", "frontend/app.js", "frontend/styles.css")
sys.path.insert(0, str(ROOT))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def health() -> dict:
    with urllib.request.urlopen("http://127.0.0.1:8787/api/health", timeout=3) as response:
        return json.load(response)


def restart(shell: Path) -> None:
    subprocess.run(["tmux", "kill-session", "-t", "reading-bench-app"], check=False, capture_output=True)
    for attempt in range(40):
        try:
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", 8787))
            break
        except OSError:
            if attempt == 39:
                raise RuntimeError("Project app port is still occupied; no unknown process was stopped")
            time.sleep(.25)
    subprocess.run(["tmux", "new-session", "-d", "-s", "reading-bench-app", "-c", str(ROOT), "sh " + shlex.quote(str(shell))], check=True)
    for attempt in range(40):
        try:
            if health().get("status") == "ok":
                return
        except OSError:
            pass
        time.sleep(.25)
    raise RuntimeError("Project app did not become healthy")


def main() -> None:
    from backend import server

    if os.name == "nt":
        raise RuntimeError("This deployment helper is for the project Linux server")
    if any(run.get("status") in {"queued", "running"} for run in server.all_objects("run")):
        raise RuntimeError("Active project evaluations must finish before deploying")
    stage = FOLDER / "staged"
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != set(FILES):
        raise ValueError("Unexpected staged deployment files")
    for name in FILES:
        path = stage / name
        if sha(path) != manifest[name]:
            raise ValueError("Staged hash mismatch: " + name)
        if path.suffix == ".py":
            compile(path.read_bytes(), str(path), "exec")
    pid = subprocess.check_output(["tmux", "display-message", "-t", "reading-bench-app", "-p", "#{pane_pid}"], text=True).strip()
    if not pid.isdigit():
        raise RuntimeError("Project app PID unavailable")
    process = Path("/proc") / pid
    command = (process / "cmdline").read_bytes().replace(b"\0", b" ")
    environment = dict(part.split("=", 1) for part in (process / "environ").read_text().split("\0") if "=" in part)
    if b"-m backend.server" not in command or environment.get("READING_BENCH_DATA_DIR") != str(ROOT / "var"):
        raise RuntimeError("Named tmux session is not the isolated project app")
    snapshot = FOLDER / time.strftime("before-demo-%Y%m%dT%H%M%SZ", time.gmtime())
    snapshot.mkdir(parents=True, exist_ok=False)
    backup = snapshot / "bench.sqlite3"
    with sqlite3.connect(server.DB) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    previous = {}
    for name in FILES:
        current = ROOT / name
        previous[name] = current.exists()
        if current.exists():
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, destination)
    variables = {k: v for k, v in environment.items() if k.startswith("READING_BENCH_")}
    variables["READING_BENCH_DEPLOYMENT_LABEL"] = "服务器 · RTX 3090"
    shell = FOLDER / "app-demo.sh"
    shell.write_text("#!/bin/sh\nexec env " + " ".join(shlex.quote(k + "=" + v) for k, v in variables.items()) + " " +
                     shlex.quote(str(ROOT / ".venv/bin/python")) + " -u -m backend.server >>" +
                     shlex.quote(str(FOLDER / "app-demo.log")) + " 2>&1\n", encoding="utf-8")
    shell.chmod(0o700)
    try:
        for name in FILES:
            destination = ROOT / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / name, destination)
        restart(shell)
        with urllib.request.urlopen("http://127.0.0.1:8787/api/demo/status", timeout=60) as response:
            demo = json.load(response)
    except Exception:
        for name, existed in previous.items():
            destination = ROOT / name
            if existed:
                shutil.copy2(snapshot / name, destination)
            elif destination.exists():
                destination.unlink()
        restart(shell)
        raise
    result = {"health": health(), "deployed_files": manifest, "previous_files": previous,
              "backup": {"path": str(backup), "sha256": sha(backup)}, "demo_ready": demo.get("ready"),
              "model_calls": 0}
    (FOLDER / "deployment.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"health": result["health"], "demo_ready": result["demo_ready"], "backup": str(backup), "model_calls": 0}))


if __name__ == "__main__":
    main()
