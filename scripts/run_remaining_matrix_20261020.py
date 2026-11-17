"""Complete the last three historical models and separate synthetic diagnostic."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LAST = ["qwen25-14b", "mistral03-7b", "internlm25-7b"]
ALL = ["qwen25-15b", "qwen25-3b", "qwen25-7b", "llama31-8b", *LAST]

def main() -> None:
    stages = [
        ("main-last3", LAST, "dev-expanded-20261020", ["--modes", "with_context"]),
        ("diagnostic-last3", LAST, "dev-expanded-20261020", ["--modes", "no_context", "--question-ids", "q01", "q02", "q03", "q04"]),
        ("counterfactual", ALL, "dev-counterfactual-20261020", ["--modes", "with_context"]),
    ]
    outcomes = []
    for stage, models, bank, extra in stages:
        command = [sys.executable, "-u", "-m", "scripts.run_model_matrix", "--base-url", "http://127.0.0.1:8787", "--ollama-url", "http://127.0.0.1:11435", "--models", *models, "--bank", bank, "--strict-budget", "false", "--poll-seconds", "10", "--output-dir", "output/model-matrix-20261020-" + stage, *extra]
        status = subprocess.run(command, cwd=ROOT).returncode
        outcomes.append({"stage": stage, "returncode": status, "command": command})
        (ROOT / "output/remaining-matrix-stage-status-20261020.json").write_text(json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
        if status not in {0, 1}:
            raise SystemExit(status)

if __name__ == "__main__":
    main()
