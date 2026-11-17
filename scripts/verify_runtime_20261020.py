"""Read-only final service and GPU inventory; does not invoke a model."""
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request


def get(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def main():
    root = Path(__file__).resolve().parents[1]
    result = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "health": get("http://127.0.0.1:8787/api/health"),
        "ollama_version": get("http://127.0.0.1:11435/api/version"),
        "resident_models": get("http://127.0.0.1:11435/api/ps"),
        "gpu_inventory": subprocess.check_output([
            "nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits"], text=True).strip(),
        "project_sessions": subprocess.check_output(["tmux", "list-sessions"], text=True).strip(),
        "free_disk_bytes": shutil.disk_usage(root).free,
        "sqlite_backup_exists": (root / "runtime/deployments/20261020/bench-final.sqlite3").is_file(),
        "model_directory": str(root / "runtime/models"),
        "model_inference_calls": 0,
    }
    assert result["sqlite_backup_exists"]
    path = root / "output/final-runtime-check-20261020.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
