"""Exercise the demo page's real HTTP API and preserve its actual exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", default="qwen25-7b")
    parser.add_argument("--preset", default="zh-reading")
    parser.add_argument("--execute", action="store_true", help="Explicitly authorize one real preset run; checks alone never infer")
    args = parser.parse_args()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": "Bearer " + os.environ["READING_BENCH_TOKEN"]} if os.environ.get("READING_BENCH_TOKEN") else {}

    def request(path: str, body: dict | None = None) -> bytes:
        req = urllib.request.Request(args.base_url.rstrip("/") + path,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={**headers, **({"Content-Type": "application/json"} if body is not None else {})})
        with urllib.request.urlopen(req, timeout=75) as response:
            return response.read()

    def get(path: str, body: dict | None = None) -> dict:
        return json.loads(request(path, body))

    def save(name: str, data: dict) -> None:
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = get("/api/demo/status")
    save("status-before.json", status)
    asset_hashes = {}
    for name in ("app.js", "styles.css", "index.html"):
        served = request("/" if name == "index.html" else "/" + name)
        served_sha = hashlib.sha256(served).hexdigest()
        if served_sha != hashlib.sha256((ROOT / "frontend" / name).read_bytes()).hexdigest():
            raise ValueError("Deployed frontend hash mismatch: " + name)
        asset_hashes[name] = served_sha
    if not args.execute:
        save("verification.json", {"ready": status["ready"], "frontend_hashes": asset_hashes, "model_calls": 0})
        print(json.dumps({"ready": status["ready"], "model_calls": 0}))
        return
    plan_path = out / "plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if any(plan[key] != value for key, value in {"base_url": args.base_url, "model_id": args.model, "preset_id": args.preset}.items()):
            raise ValueError("Use a new output directory for a different demo plan")
    else:
        plan = {"base_url": args.base_url, "model_id": args.model, "preset_id": args.preset,
                "client_request_id": "live-demo-check-" + uuid.uuid4().hex, "allow_draft": True}
        save("plan.json", plan)
    body = {key: value for key, value in plan.items() if key != "base_url"}
    created = get("/api/demo/runs", body)
    identity = created["run_id"]
    save("created.json", created)
    repeated = get("/api/demo/runs", body)
    if repeated["run_id"] != identity or not repeated["reused"]:
        raise ValueError("Idempotent retry created another run")
    save("idempotent-retry.json", repeated)
    deadline, prior = time.monotonic() + 720, None
    while True:
        run = get("/api/v2/runs/" + identity)
        progress = {"run_id": identity, "status": run["status"], "progress": run["progress"]}
        if progress != prior:
            print(json.dumps(progress), flush=True)
            prior = progress
        if run["status"] not in {"queued", "running"}:
            break
        if time.monotonic() >= deadline:
            save("last-pending-run.json", run)
            raise TimeoutError("Run retained on platform; rerun this same plan to inspect without duplicate generation")
        time.sleep(1.5)
    exported = request("/api/v2/runs/" + identity + "/export?format=json")
    (out / (identity + ".json")).write_bytes(exported)
    if json.loads(exported) != run:
        raise ValueError("Reloaded run and JSON export differ")
    csv_data = request("/api/v2/runs/" + identity + "/export?format=csv")
    (out / (identity + ".csv")).write_bytes(csv_data)
    rows = list(csv.DictReader(io.StringIO(csv_data.decode("utf-8-sig"))))
    if len(rows) != len(run["results"]) or run["progress"]["done"] != run["progress"]["total"]:
        raise ValueError("Completed row count mismatch")
    for row, flat in zip(run["results"], rows):
        if flat["raw_response"] != row.get("raw_response", "") or flat["question_id"] != row["question_id"]:
            raise ValueError("CSV raw result mismatch")
    if len(run["attempts"]) != len(run["results"]) or not all(r.get("raw_response") or r.get("error") for r in run["results"]):
        raise ValueError("Missing actual attempt or response evidence")
    result = {"run_id": identity, "status": run["status"], "base_url": args.base_url,
              "preset_id": args.preset, "model_id": args.model, "progress": run["progress"],
              "actual_model_call_attempts": len(run["attempts"]), "response_errors": sum(bool(r.get("error")) for r in run["results"]),
              "idempotent_retry_same_run": True, "reload_export_match": True, "csv_rows": len(rows),
              "frontend_hashes": asset_hashes, "formal": run["formal"],
              "artifacts": [{"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                            for p in sorted(out.iterdir()) if p.is_file() and p.name != "verification.json"]}
    save("verification.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if run["status"] != "completed":
        raise RuntimeError("Real run retained with terminal failure; review the saved raw evidence")


if __name__ == "__main__":
    main()
