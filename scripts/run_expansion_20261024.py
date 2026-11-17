"""Sequential, resumable expansion stages. No implicit re-answering of errors."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/expansion-20261024"


def configurations(stage: str) -> list[dict]:
    if stage in {"bridge", "anchor"}:
        common = {"models": ["qwen25-7b"] if stage == "anchor" else ["gemma2-9b", "phi35-mini"], "bank": "dev-expanded-20261020", "num_ctx": 8192, "strict_time": "true"}
        return [{**common, "name": stage + "-main", "mode": "with_context"},
                {**common, "name": stage + "-control", "mode": "no_context", "question_ids": ["q01", "q02", "q03", "q04"]},
                {**common, "name": stage + "-counterfactual", "mode": "with_context", "bank": "dev-counterfactual-20261020"}]
    if stage == "reference":
        return [{"name": "reference-" + name, "models": ["qwen25-7b", "phi35-mini"],
                 "bank": "reference-" + name + "-20261025", "mode": "with_context", "num_ctx": 8192, "strict_time": "false"}
                for name in ("squad2", "cmrc2018")]
    if stage == "recent":
        return [{"name": "recent-main", "models": ["qwen25-7b", "gemma2-9b"], "bank": "dev-recent-additions-20261024",
                 "mode": "with_context", "num_ctx": 8192, "strict_time": "true"}]
    if stage == "yi":
        selection = json.loads((OUT / "four-k-selection.json").read_text(encoding="utf-8"))
        return [{"name": "four-k-" + name + "-" + mode, "models": ["qwen25-7b", "yi15-6b"],
                 "bank": "reference-" + name + "-20261025", "mode": mode, "num_ctx": 4096,
                 "strict_time": "false", "article_ids": selection[name]["article_ids"]}
                for name in ("squad2", "cmrc2018") for mode in ("with_context", "no_context")]
    raise ValueError(stage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["bridge", "reference", "recent", "yi", "anchor"], required=True)
    args = parser.parse_args()
    stages = configurations(args.stage)
    OUT.mkdir(parents=True, exist_ok=True)
    plan = {"schema_version": "reading-expansion-stage-v1", "stage": args.stage, "configurations": stages,
            "settings": {"temperature": 0, "seed": 42, "max_tokens": 512, "strict_budget": False},
            "formal": False, "notice": "Public historical reference and recent AI-draft banks stay separate; no contamination-free or formal ranking claim."}
    plan_path = OUT / (args.stage + "-plan.json")
    if plan_path.exists() and json.loads(plan_path.read_text(encoding="utf-8")) != plan:
        raise ValueError("Stage plan changed; refuse mixing runs")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    statuses = []
    for configuration in stages:
        directory = OUT / configuration["name"]
        command = [sys.executable, "-u", "-m", "scripts.run_model_matrix", "--base-url", "http://127.0.0.1:8787",
                   "--ollama-url", "http://127.0.0.1:11435", "--bank", configuration["bank"], "--models", *configuration["models"],
                   "--modes", configuration["mode"], "--strict-budget", "false", "--strict-time", configuration["strict_time"],
                   "--num-ctx", str(configuration["num_ctx"]), "--poll-seconds", "15", "--output-dir", str(directory)]
        for field, option in (("article_ids", "--article-ids"), ("question_ids", "--question-ids")):
            if field in configuration:
                command += [option, *configuration[field]]
        result = subprocess.run(command, cwd=ROOT)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8")) if (directory / "manifest.json").exists() else {}
        complete = result.returncode in {0, 1} and bool(manifest.get("jobs")) and all(
            job.get("complete") is True and job.get("final_status") == "completed" and job.get("status") == "exported" for job in manifest["jobs"])
        statuses.append({"name": configuration["name"], "complete": complete, "exit_code": result.returncode,
                         "rows": sum(job.get("progress", {}).get("done", 0) for job in manifest.get("jobs", [])),
                         "response_errors": sum(job.get("errors", 0) for job in manifest.get("jobs", []))})
        (OUT / (args.stage + "-status.json")).write_text(json.dumps({"stage": args.stage, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "complete": complete and len(statuses) == len(stages), "matrices": statuses}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not complete:
            raise RuntimeError("Stage stopped; preserve existing run and reconcile explicitly: " + configuration["name"])


if __name__ == "__main__":
    main()
