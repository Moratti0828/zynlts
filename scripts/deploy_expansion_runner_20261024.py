"""Idle-only deployment of the staged v2 runner; preserve the earlier source."""
from __future__ import annotations
import json
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from backend import server
    if any(r["status"] in {"running", "queued"} for r in server.all_objects("run")):
        raise RuntimeError("Do not restart an active model evaluation")
    folder = ROOT / "runtime/deployments/20261024"
    stage = folder / "experiment_v2.new.py"
    current = ROOT / "backend/experiment_v2.py"
    backup = folder / "experiment_v2.before.py"
    pane = subprocess.check_output(["tmux", "display-message", "-t", "reading-bench-app", "-p", "#{pane_pid}"], text=True).strip()
    if not pane.isdigit():
        raise RuntimeError("Cannot identify the project app process")
    process = Path("/proc") / pane
    command = (process / "cmdline").read_bytes().replace(b"\0", b" ").decode()
    environment = dict(part.split("=", 1) for part in (process / "environ").read_bytes().decode().split("\0") if "=" in part)
    if "-m backend.server" not in command or environment.get("READING_BENCH_DATA_DIR") != str(ROOT / "var"):
        raise RuntimeError("Named tmux process is not the isolated project app")
    if not backup.exists():
        backup.write_bytes(current.read_bytes())
    compile(stage.read_bytes(), str(stage), "exec")
    current.write_bytes(stage.read_bytes())
    workspace_stage = folder / "corpus_workspace.new.py"
    if workspace_stage.exists():
        workspace = ROOT / "backend/corpus_workspace.py"
        saved = folder / "corpus_workspace.before.py"
        compile(workspace_stage.read_bytes(), str(workspace_stage), "exec")
        if not saved.exists():
            saved.write_bytes(workspace.read_bytes())
        workspace.write_bytes(workspace_stage.read_bytes())
    variables = {k: v for k, v in environment.items() if k.startswith("READING_BENCH_")}
    shell = folder / "app-v22.sh"
    shell.write_text("#!/bin/sh\nexec env " + " ".join(shlex.quote(k + "=" + v) for k, v in variables.items()) + " " +
                     shlex.quote(str(ROOT / ".venv/bin/python")) + " -u -m backend.server >>" + shlex.quote(str(folder / "app-v22.log")) + " 2>&1\n")
    subprocess.run(["tmux", "kill-session", "-t", "reading-bench-app"], check=True)
    for attempt in range(40):
        try:
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", 8787))
            break
        except OSError:
            if attempt == 39:
                raise RuntimeError("App port not released; no unknown process was stopped")
            time.sleep(.5)
    subprocess.run(["tmux", "new-session", "-d", "-s", "reading-bench-app", "-c", str(ROOT), "sh " + shlex.quote(str(shell))], check=True)
    for attempt in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8787/api/health", timeout=3) as response:
                health = json.load(response)
            print(json.dumps({"health": health, "backup": str(backup), "runner": "v2.2-context-reference-20261024"}))
            return
        except OSError:
            if attempt == 29:
                raise
            time.sleep(.5)


if __name__ == "__main__":
    main()
