"""Move only the idle project Ollama to a free GPU, retaining its model store."""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import shlex
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from backend import server
    assert str(ROOT) == "/home/jmy/reading-bench"
    active = [r["id"] for r in server.all_objects("run") if r["status"] in {"running", "queued"}]
    if active:
        raise RuntimeError("Project has active runs; retain its server: " + repr(active))
    inventory = subprocess.check_output(["nvidia-smi", "--query-gpu=index,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True)
    gpu_one = next(line for line in inventory.splitlines() if line.split(",")[0].strip() == "1")
    _, used, utilization = map(int, gpu_one.split(","))
    if used > 512 or utilization > 10:
        raise RuntimeError("GPU1 is not free; do not alter another user's workload")
    pane_result = subprocess.run(["tmux", "display-message", "-t", "reading-bench-ollama", "-p", "#{pane_pid}"], capture_output=True, text=True)
    has_pane = pane_result.returncode == 0 and pane_result.stdout.strip().isdigit()
    environment = {}
    if has_pane:
        process = Path("/proc") / pane_result.stdout.strip()
        command = (process / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        environment = dict(item.split("=", 1) for item in (process / "environ").read_bytes().decode().split("\0") if "=" in item)
        if "ollama serve" not in command or environment.get("OLLAMA_MODELS") != str(ROOT / "runtime/models"):
            raise RuntimeError("The named tmux session is not the isolated project Ollama")
    folder = ROOT / "runtime/deployments/20261024"
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / "bench-before-expansion.sqlite3"
    if not backup.exists():
        with sqlite3.connect(server.DB) as source, sqlite3.connect(backup) as target:
            source.backup(target)
    previous = {k: v for k, v in environment.items() if k.startswith("OLLAMA_") or k == "CUDA_VISIBLE_DEVICES"}
    if environment.get("CUDA_VISIBLE_DEVICES") != "1":
        variables = {"CUDA_VISIBLE_DEVICES": "1", "OLLAMA_HOST": "127.0.0.1:11435",
                     "OLLAMA_MODELS": str(ROOT / "runtime/models"), "OLLAMA_MAX_LOADED_MODELS": "1",
                     "OLLAMA_NUM_PARALLEL": "1"}
        script = folder / "ollama-gpu1.sh"
        script.write_text("#!/bin/sh\nexec env " + " ".join(shlex.quote(k + "=" + v) for k, v in variables.items()) +
                          " /usr/local/bin/ollama serve >>" + shlex.quote(str(folder / "ollama-gpu1.log")) + " 2>&1\n")
        if has_pane:
            subprocess.run(["tmux", "kill-session", "-t", "reading-bench-ollama"], check=True)
        # A tmux session may exit before its listening process releases the port.
        for attempt in range(40):
            try:
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 11435))
                break
            except OSError:
                if attempt == 39:
                    raise RuntimeError("Port still occupied; no unknown process was stopped")
                time.sleep(.5)
        subprocess.run(["tmux", "new-session", "-d", "-s", "reading-bench-ollama", "-c", str(ROOT), "sh " + shlex.quote(str(script))], check=True)
    for attempt in range(20):
        try:
            with urllib.request.urlopen("http://127.0.0.1:11435/api/version", timeout=3) as response:
                version = json.load(response)
            break
        except OSError:
            if attempt == 19:
                raise
            time.sleep(.5)
    record = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "project_gpu": 1,
              "previous_project_environment": previous, "gpu_inventory_before": inventory,
              "backup": str(backup), "ollama_version": version, "other_project_processes_changed": False}
    (ROOT / "output/server-gpu1-preparation-20261024.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
