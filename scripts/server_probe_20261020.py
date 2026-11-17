"""Read-only GPU, project-service and resource evidence on the Linux server."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.request import urlopen


def command(args: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(args, text=True, capture_output=True, timeout=25)
        return {"argv": args, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": args, "error": str(exc)}


def request(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=10) as response:
            return {"url": url, "status": response.status, "data": json.load(response)}
    except (OSError, ValueError) as exc:
        return {"url": url, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()
    if not args.device.isdecimal():
        parser.error("device must be a physical numeric GPU index")
    os.environ["CUDA_VISIBLE_DEVICES"] = args.device
    commands = {
        "host": ["uname", "-a"],
        "gpu": ["nvidia-smi", "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu", "--format=csv"],
        "compute_processes": ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory", "--format=csv"],
        "disk": ["df", "-B1", "/home/jmy/reading-bench"],
        "tmux": ["tmux", "list-sessions"],
        "ports": ["ss", "-lntp"],
        "models_size": ["du", "-sb", "/home/jmy/reading-bench/runtime/models"],
        "ollama_version": ["/usr/local/bin/ollama", "--version"],
    }
    record: dict[str, Any] = {
        "recorded_at_server_utc": datetime.now(timezone.utc).isoformat(),
        "project": "/home/jmy/reading-bench",
        "commands": {key: command(value) for key, value in commands.items()},
        "http": {key: request(url) for key, url in {
            "models": "http://127.0.0.1:11435/api/tags",
            "loaded_models": "http://127.0.0.1:11435/api/ps",
            "health": "http://127.0.0.1:8787/api/health",
            "runs": "http://127.0.0.1:8787/api/runs",
        }.items()},
    }
    compute = record["commands"]["compute_processes"].get("stdout", "")
    pids = []
    for row in compute.splitlines()[1:]:
        fields = row.split(",")
        if len(fields) >= 2 and fields[1].strip().isdigit():
            pids.append(fields[1].strip())
    record["compute_owners"] = command(["ps", "-p", ",".join(pids), "-o", "pid,user,comm"]) if pids else {"pids": []}
    try:
        driver = ctypes.CDLL("libcuda.so.1")
        init = driver.cuInit(0)
        count = ctypes.c_int()
        count_code = driver.cuDeviceGetCount(ctypes.byref(count))
        record["cuda"] = {"physical_device": args.device, "cuInit_code": init, "cuDeviceGetCount_code": count_code, "device_count": count.value, "ready": init == 0 and count_code == 0 and count.value > 0}
    except OSError as exc:
        record["cuda"] = {"physical_device": args.device, "ready": False, "error": str(exc)}
    rendered = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
