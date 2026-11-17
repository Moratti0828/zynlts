"""Run the first four ready models while the other weights download."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["qwen25-15b", "qwen25-3b", "qwen25-7b", "llama31-8b"]

def main() -> None:
    stages = [
        ("main-first4", ["--modes", "with_context"]),
        ("diagnostic-first4", ["--modes", "no_context", "--question-ids", "q01", "q02", "q03", "q04"]),
    ]
    outcomes = []
    for stage, extra in stages:
        command = [sys.executable, "-u", "-m", "scripts.run_model_matrix", "--base-url", "http://127.0.0.1:8787", "--ollama-url", "http://127.0.0.1:11435", "--models", *MODELS, "--bank", "dev-expanded-20261020", "--strict-budget", "false", "--poll-seconds", "10", "--output-dir", "output/model-matrix-20261020-" + stage, *extra]
        status = subprocess.run(command, cwd=ROOT).returncode
        outcomes.append({"stage": stage, "returncode": status, "command": command})
        (ROOT / "output" / "initial-matrix-stage-status-20261020.json").write_text(json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
        # One means completed runs contain retained model/format errors. Two
        # means a transport/identity/admission failure requiring investigation.
        if status not in {0, 1}:
            raise SystemExit(status)

if __name__ == "__main__":
    main()
