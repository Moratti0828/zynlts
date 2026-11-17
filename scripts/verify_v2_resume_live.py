"""Exercise cancel/resume against a running app using two real draft questions."""
import argparse
import json
from pathlib import Path
import time
import urllib.request


parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://127.0.0.1:8788")
parser.add_argument("--output", type=Path, default=Path("output/v2-resume-live-20261013.json"))
args = parser.parse_args()


def request(path, body=None):
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(args.base_url.rstrip("/") + path, data=payload,
        headers={"Content-Type": "application/json"} if payload is not None else {})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def settled(identity):
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        run = request("/api/v2/runs/" + identity)
        if run["status"] not in {"queued", "running"}:
            return run
        time.sleep(0.25)
    raise TimeoutError("Experiment did not finish")


created = request("/api/v2/runs", {"bank_id": "dev-pilot-v2", "model_ids": ["qwen25-7b"],
    "question_ids": ["q01"], "allow_draft": True, "strict_time": True,
    "strict_budget": True, "mode": "with_context", "max_tokens": 512,
    "temperature": 0, "bootstrap_repetitions": 0})
identity = created["id"]
cancel = request("/api/runs/" + identity + "/cancel", {})
stopped = settled(identity)
assert stopped["status"] == "cancelled", stopped["status"]
assert len(stopped["results"]) < len(stopped["plan"]), "Cancellation arrived after all tasks"
original_rows = json.loads(json.dumps(stopped["results"]))
resume = request("/api/v2/runs/" + identity + "/resume", {})
final = settled(identity)
assert final["status"] == "completed", final.get("error")
assert len(final["results"]) == 2
keys = [(r["model_id"], r["article_id"], r["question_id"]) for r in final["results"]]
assert len(set(keys)) == len(keys)
assert final["results"][:len(original_rows)] == original_rows
assert all(r["budget"]["runtime_count_matches"] for r in final["results"])
assert all(r.get("attempt_id") for r in final["results"])
assert len(final["attempts"]) == len(final["results"])
record = {"purpose": "Real cancel/resume engineering verification, not a formal model score",
    "base_url": args.base_url, "created": created, "cancel": cancel,
    "stopped_progress": stopped["progress"], "resume": resume,
    "existing_rows_unchanged": True, "duplicate_results": 0, "final_run": final}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"id": identity, "status": final["status"],
    "stopped": stopped["progress"], "finished": final["progress"],
    "attempts": len(final["attempts"]), "duplicates": 0,
    "runtime_tokens_match": True, "output": str(args.output)}, ensure_ascii=False))
