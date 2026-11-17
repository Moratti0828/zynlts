"""Append official historical InternLM without replacing registry-variant runs."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    while True:
        path = ROOT / "output/remaining-matrix-stage-status-20261020.json"
        try:
            statuses = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            statuses = []
        if len(statuses) == 3:
            if any(x["returncode"] not in {0, 1} for x in statuses):
                raise RuntimeError("Preceding matrix requires repair")
            break
        if subprocess.run(["tmux", "has-session", "-t", "reading-bench-matrix-20261020-last3"], capture_output=True).returncode:
            raise RuntimeError("Preceding matrix exited before all three stages completed")
        time.sleep(10)
    stages = [
        ("official-main", "dev-expanded-20261020", ["--modes", "with_context"]),
        ("official-diagnostic", "dev-expanded-20261020", ["--modes", "no_context", "--question-ids", "q01", "q02", "q03", "q04"]),
        ("official-counterfactual", "dev-counterfactual-20261020", ["--modes", "with_context"]),
    ]
    outcomes = []
    for stage, bank, extra in stages:
        command = [sys.executable, "-u", "-m", "scripts.run_model_matrix", "--base-url", "http://127.0.0.1:8787", "--ollama-url", "http://127.0.0.1:11435", "--models", "internlm25-7b-official2024", "--bank", bank, "--strict-budget", "false", "--poll-seconds", "10", "--output-dir", "output/model-matrix-20261020-" + stage, *extra]
        result = subprocess.run(command, cwd=ROOT).returncode
        outcomes.append({"stage": stage, "returncode": result, "command": command})
        (ROOT / "output/official-matrix-stage-status-20261020.json").write_text(json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
        if result not in {0, 1}:
            raise SystemExit(result)

if __name__ == "__main__":
    main()
