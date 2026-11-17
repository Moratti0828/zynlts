"""Verify the saved source, real-run and resume artifacts without model calls."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from backend.corpus_workspace import _body


root = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((root / name).read_text(encoding="utf-8-sig"))


selection = read("data/annotation/development-selection-20261013.json")
records = selection["records"]
assert len(records) == len({r["id"] for r in records}) == 20
assert Counter(r["language"] for r in records) == {"zh": 10, "en": 10}
assert selection["human_review_count"] == 0 and not selection["formal"]
for record in records:
    _body(record, root)
    raw = (root / record["raw_path"]).resolve()
    assert raw.is_relative_to((root / "data" / "candidates").resolve())
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == record["raw_sha256"]
assert "en-nih-3d1dab450396" not in {r["id"] for r in records}

run = read("output/v2-qwen16-live-20261013.json")
assert run["status"] == "completed" and not run["formal"]
assert len(run["plan"]) == len(run["results"]) == 16
assert len({(r["model_id"], r["article_id"], r["question_id"]) for r in run["results"]}) == 16
assert Counter(r["language"] for r in run["results"]) == {"zh": 8, "en": 8}
assert sum(bool(r["error"]) for r in run["results"]) == 3
assert all(r["budget"]["runtime_count_matches"] for r in run["results"])
with (root / "output/v2-qwen16-live-20261013.csv").open(encoding="utf-8-sig", newline="") as handle:
    assert len(list(csv.DictReader(handle))) == 16

resume = read("output/v2-resume-live-20261013.json")
assert resume["stopped_progress"] == {"done": 1, "total": 2}
assert resume["resume"]["remaining"] == 1 and resume["duplicate_results"] == 0
assert resume["existing_rows_unchanged"]
final = resume["final_run"]
assert final["status"] == "completed" and final["progress"] == {"done": 2, "total": 2}
assert len(final["attempts"]) == 2
assert all(a["status"] == "recorded_response" for a in final["attempts"])
assert all(r["attempt_id"] in {a["id"] for a in final["attempts"]} for r in final["results"])

server = read("output/server-v2-deployment-20261013.json")
assert server["health_current"]["version"] == "1.2.0"
assert server["acceptance_passed"] and not server["models_downloaded"]
server_run = server["acceptance_run"]
assert server_run["status"] == "completed" and not server_run["formal"]
server_row = server_run["results"][0]
assert server_row["budget"]["runtime_count_matches"]
assert server_row["input_tokens"] == server_row["budget"]["input_tokens"] == 408
assert server_row["metrics"]["answer_correct"] == 1
assert server_row["metrics"]["evidence_exact"] == 0
assert all(m["size_vram"] == 0 for m in server["ollama_runtime_ps"]["models"])
full_attempt = server["initial_full_passage_acceptance"]
assert full_attempt["status"] == "failed" and full_attempt["results"][0]["error"]
assert full_attempt["results"][0]["latency_s"] >= 170
corpus = server["corpus_sync"]
assert corpus["status"] == "verified"
assert corpus["counts_after"]["downloaded"] == 402
assert corpus["counts_after"]["language"] == {"zh": 168, "en": 234}
assert corpus["counts_after"]["states"]["human_reviewed"] == 0
assert corpus["counts_after"]["states"]["frozen"] == 0
assert all(x["api_hash_verified"] and x["hash_matches_local"] for x in corpus["body_examples_verified"].values())

files = ["backend/experiment_v2.py", "backend/benchmark_v2.py", "backend/token_budget.py",
    "backend/server.py", "frontend/app.js", "frontend/styles.css", "data/benchmark-spec-v2.json",
    "data/annotation/dev-pilot-v2.json", "data/annotation/development-selection-20261013.json",
    "output/v2-qwen16-live-20261013.json", "output/v2-qwen16-live-20261013.csv",
    "output/v2-resume-live-20261013.json", "output/v2-platform-20261013.png",
    "docs/platform-v2-execution-20261013.md", "output/server-v2-deployment-20261013.json",
    "output/server-v2-corpus-api-verification-20261013.json"]
report = {"verification": "saved_real_run_and_source_artifacts_checked_without_model_calls",
    "as_of_client_date": "2026-10-13", "passed": True,
    "real_draft_run": {"id": run["id"], "questions": 16, "response_contract_errors": 3,
        "runtime_token_count_matches": 16, "formal": False},
    "real_resume_run": {"id": final["id"], "completed_before_cancel": 1,
        "remaining_called_after_resume": 1, "result_duplicates": 0, "attempts": 2},
    "development_selection": {"articles": 20, "zh": 10, "en": 10,
        "body_and_raw_hashes_verified": 20, "human_reviewed": 0, "new_authored_questions": 0},
    "server": {"application_version": "1.2.0", "run": server_run["id"],
        "mode": "cpu_single_paragraph_engineering_draft", "runtime_input_tokens": 408,
        "answer_correct": True, "evidence_correct": False,
        "full_passage_attempt_timed_out": True, "new_weights_downloaded": False,
        "candidate_articles_synced": 402, "candidate_languages": {"zh": 168, "en": 234}},
    "files": [{"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()} for name in files]}
(root / "output/platform-v2-verification-20261013.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in report.items() if k != "files"}, ensure_ascii=False))
