"""Idle-only consistent backup and read-only service evidence, no inference."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    from backend import server
    out = ROOT / "output/expansion-20261024"
    for stage in ("bridge", "reference", "yi", "recent", "anchor"):
        if read(out / (stage + "-status.json")).get("complete") is not True:
            raise RuntimeError("Stage incomplete: " + stage)
    if any(run["status"] in {"running", "queued"} for run in server.all_objects("run")):
        raise RuntimeError("Active project runs retained; do not finalize yet")
    jobs = [job for path in out.glob("*/manifest.json") for job in read(path)["jobs"]]
    assert len(jobs) == 23 and sum(job["progress"]["done"] for job in jobs) == 1862
    assert all(job["complete"] and job["final_status"] == "completed" and job["status"] == "exported" for job in jobs)
    pid = subprocess.check_output(["tmux", "display-message", "-t", "reading-bench-ollama", "-p", "#{pane_pid}"], text=True).strip()
    if not pid.isdigit():
        raise RuntimeError("Project Ollama tmux process unavailable")
    environment = dict(value.split("=", 1) for value in (Path("/proc") / pid / "environ").read_bytes().decode().split("\0") if "=" in value)
    gpu_environment = {k: environment.get(k) for k in ("CUDA_VISIBLE_DEVICES", "OLLAMA_HOST", "OLLAMA_MODELS", "OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_LOADED_MODELS")}
    assert gpu_environment["CUDA_VISIBLE_DEVICES"] == "1" and gpu_environment["OLLAMA_MODELS"] == str(ROOT / "runtime/models")
    backup = ROOT / "runtime/deployments/20261024/bench-after-expansion-20261025.sqlite3"
    if backup.exists():
        raise FileExistsError("Keep the prior final backup; choose another explicit version")
    with sqlite3.connect(server.DB) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    records = [{"id": job["run_id"], "model_id": job["model_id"], "mode": job["mode"],
                "progress": job["progress"], "errors": job["errors"], "gpu_observed": job.get("gpu_observed"),
                "gpu_fully_resident_observed": job.get("gpu_fully_resident_observed")} for job in jobs]
    state = {"client_date": "2026-10-25", "captured_at": server.now(), "health": get("http://127.0.0.1:8787/api/health"),
             "models": get("http://127.0.0.1:8787/api/models")["models"], "banks": get("http://127.0.0.1:8787/api/v2/banks")["banks"],
             "ollama_version": get("http://127.0.0.1:11435/api/version"), "ollama_residency": get("http://127.0.0.1:11435/api/ps"),
             "gpu": subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], text=True),
             "project_gpu": 1, "project_ollama_environment": gpu_environment,
             "sessions": subprocess.check_output(["tmux", "list-sessions"], text=True),
             "backup": {"path": str(backup), "sha256": sha(backup), "bytes": backup.stat().st_size},
             "runs": records, "total_rows": 1862, "total_response_errors": sum(job["errors"] for job in jobs),
             "new_model_inference_calls_from_this_probe": 0, "formal": False, "human_review_count": 0}
    (ROOT / "output/final-platform-state-20261025.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"models": len(state["models"]), "new_runs": len(records), "rows": 1862,
                      "errors": state["total_response_errors"], "backup": str(backup), "health": state["health"]}))


if __name__ == "__main__":
    main()
