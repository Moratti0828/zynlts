"""Bounded, same-task completion: wait for all stages, reload idle app, backup."""
import json
import subprocess
import sys
from scripts.run_expansion_tail_20261025 import ROOT, OUT, wait_for


if __name__ == "__main__":
    for stage in ("bridge", "reference", "yi", "recent", "anchor"):
        wait_for(OUT / (stage + "-status.json"), lambda value: value.get("complete") is True)
    subprocess.run([sys.executable, "-u", "-m", "scripts.deploy_expansion_runner_20261024"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-u", "-m", "scripts.finalize_expansion_20261025"], cwd=ROOT, check=True)
    (OUT / "finish-status.json").write_text(json.dumps({"complete": True, "all_stages_complete": True,
        "new_inference_calls": 0, "backup_created": True}) + "\n", encoding="utf-8")
