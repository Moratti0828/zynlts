"""Run one frozen v2 bank sequentially through the platform HTTP API.

Restart with the identical arguments to continue from manifest.json. A lost
creation response is deliberately NOT retried: reconcile its existing run ID.
No model transport, prompt rewriting or post-hoc answer retries live here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

SCHEMA = "reading-model-matrix-v1"
ACTIVE = {"queued", "running"}
RESUMABLE = {"interrupted", "cancelled", "failed"}
QWEN7_DIGEST = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class Api:
    def __init__(self, base_url: str, timeout: float = 30):
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Use an http(s) base URL without embedded credentials")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, path: str, body: dict | None = None, raw: bool = False) -> Any:
        data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data,
            headers={"Content-Type": "application/json"} if data is not None else {})
        if os.environ.get("READING_BENCH_TOKEN"):
            request.add_header("Authorization", "Bearer " + os.environ["READING_BENCH_TOKEN"])
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
            return payload if raw else json.loads(payload)
        except urllib.error.HTTPError as exc:
            message = exc.read(4000).decode("utf-8", errors="replace")
            raise ApiError(f"HTTP {exc.code}: {message}", exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ApiError(str(exc)) from exc


def selection(bank: dict, article_ids: list[str] | None, question_ids: list[str] | None,
              limit: int | None) -> list[dict]:
    articles = bank["articles"]
    known_articles = {a["id"] for a in articles}
    if article_ids and (len(set(article_ids)) != len(article_ids) or set(article_ids) - known_articles):
        raise ValueError("Unknown or duplicate --article-ids")
    by_id = {a["id"]: a for a in articles}
    selected = [by_id[aid] for aid in article_ids] if article_ids else articles
    known_questions = {q["id"] for a in selected for q in a["questions"]}
    if question_ids and (len(set(question_ids)) != len(question_ids) or set(question_ids) - known_questions):
        raise ValueError("Unknown or duplicate --question-ids")
    items = [{"article_id": a["id"], "question_id": q["id"], "language": a["language"],
              "kind": q["kind"], "source_cluster_id": a["source_cluster_id"]}
             for a in selected for q in a["questions"] if not question_ids or q["id"] in question_ids]
    if limit is not None and not 1 <= limit <= len(items):
        raise ValueError(f"--limit must be 1..{len(items)}; refusing a silent smaller plan")
    items = items[:limit] if limit is not None else items
    if not items:
        raise ValueError("Selection contains no questions")
    return items


def strict_budget_for(model: dict, policy: str, certified_ids: list[str]) -> bool:
    if policy in {"true", "false"}:
        return policy == "true"
    if model["id"] in certified_ids:
        return True
    spec = model.get("tokenizer_spec") or {}
    return bool((spec.get("manifest_sha256") and model.get("runtime_template_kind") == "raw_rendered_prompt") or
                (model.get("provider") == "ollama" and model.get("model") == "qwen2.5:7b-instruct" and
                 model.get("digest") == QWEN7_DIGEST))


def expected_request(args: argparse.Namespace, model_id: str, mode: str, strict_budget: bool) -> dict:
    body = {"bank_id": args.bank, "model_ids": [model_id], "allow_draft": True,
            "strict_time": args.strict_time == "true", "strict_budget": strict_budget, "mode": mode,
            "num_ctx": args.num_ctx,
            "max_tokens": 512, "temperature": 0,
            "bootstrap_repetitions": args.bootstrap_repetitions}
    if args.article_ids:
        body["article_ids"] = args.article_ids
    if args.question_ids:
        body["question_ids"] = args.question_ids
    if args.limit is not None:
        body["question_limit"] = args.limit
    return body


def client_versions() -> dict:
    root = Path(__file__).resolve().parents[1]
    versions = {}
    for key, filename, name in (("grader_version", "benchmark_v2.py", "VERSION"),
                                ("runner_version", "experiment_v2.py", "RUNNER_VERSION"),
                                ("prompt_version", "experiment_v2.py", "PROMPT_VERSION")):
        source = (root / "backend" / filename).read_text(encoding="utf-8")
        match = re.search(r"^" + name + r'\s*=\s*"([^"\n]+)"', source, re.MULTILINE)
        if not match:
            raise ValueError("Cannot freeze client code version: " + key)
        versions[key] = match.group(1)
    return versions


def assert_run_identity(run: dict, job: dict, manifest: dict) -> None:
    config, snapshots = run["config"], run["snapshots"]
    if run.get("protocol") != "reading-experiment-v2":
        raise ValueError("Wrong run protocol")
    for key, value in job["request"].items():
        # The platform records the question-ID subset in its immutable bank and
        # plan, rather than duplicating it in config. Validate it below against
        # the explicit client selection, including every (article, question).
        if key == "question_ids":
            continue
        if config.get(key) != value:
            raise ValueError(f"Frozen run config mismatch: {key}")
    for key, value in {"seed": 42, "num_ctx": job["request"].get("num_ctx", 8192)}.items():
        if config.get(key) != value:
            raise ValueError(f"Required platform setting mismatch: {key}")
    if snapshots["source_bank_sha256"] != manifest["source_bank_sha256"]:
        raise ValueError("Source bank changed; use a new matrix output directory")
    if digest(snapshots["bank"]) != snapshots["bank_sha256"]:
        raise ValueError("Selected bank snapshot hash mismatch")
    expected = {(job["model_id"], p["article_id"], p["question_id"]) for p in manifest["selection"]}
    actual = [(p["model_id"], p["article_id"], p["question_id"]) for p in run["plan"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Platform plan differs from the explicit client selection")
    models = snapshots["models"]
    frozen_model = manifest["models"][job["model_id"]]
    if len(models) != 1 or any(models[0].get(k) != frozen_model.get(k)
                               for k in ("id", "provider", "model", "digest", "base_url")):
        raise ValueError("Frozen model identity changed")
    versions = {k: config.get(k) for k in ("grader_version", "prompt_version", "runner_version")}
    if not all(versions.values()):
        raise ValueError("Missing frozen runner/prompt/grader version")
    if manifest.get("versions") and versions != manifest["versions"]:
        raise ValueError("Runner/prompt/grader versions changed inside matrix")
    if manifest.get("expected_versions") and versions != manifest["expected_versions"]:
        raise ValueError("Server runner/prompt/grader differs from the preflight client code")
    manifest.setdefault("versions", versions)
    keys = [(r["model_id"], r["article_id"], r["question_id"]) for r in run.get("results", [])]
    if len(keys) != len(set(keys)) or set(keys) - expected:
        raise ValueError("Duplicate or unplanned result rows")


def freeze_job(run: dict, job: dict) -> None:
    job.update(run_id=run["id"], status=run["status"], progress=run["progress"],
               actual_config=run["config"], selected_bank_sha256=run["snapshots"]["bank_sha256"],
               actual_models=run["snapshots"]["models"],
               attempts=len(run.get("attempts", [])), last_seen_at=now())


def export_run(api: Api, output_dir: Path, run: dict, job: dict) -> None:
    run_dir = output_dir / "runs"
    run_dir.mkdir(exist_ok=True)
    identity = run["id"]
    if not re.fullmatch(r"run-[a-f0-9]{12}", identity):
        raise ValueError("Unsafe run ID")
    # Save a complete local snapshot even when the CSV export endpoint fails.
    target = run_dir / (identity + ".json")
    atomic_json(target, run)
    job["json"] = str(target.relative_to(output_dir)).replace("\\", "/")
    csv = api.request(f"/api/v2/runs/{identity}/export?format=csv", raw=True)
    csv_path = run_dir / (identity + ".csv")
    temporary = csv_path.with_suffix(".csv.tmp")
    temporary.write_bytes(csv)
    temporary.replace(csv_path)
    job.update(csv=str(csv_path.relative_to(output_dir)).replace("\\", "/"),
               json_file_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
               csv_file_sha256=hashlib.sha256(csv).hexdigest(), exported_at=now())


def observe_device(args: argparse.Namespace, manifest: dict, job: dict, run: dict) -> None:
    if not args.ollama_url:
        return
    observation = {"at": now(), "run_id": run["id"], "job": job["key"],
                   "run_status": run["status"], "progress": run["progress"], "models": []}
    try:
        payload = Api(args.ollama_url, min(args.request_timeout, 5)).request("/api/ps")
        fields = ("name", "model", "digest", "size", "size_vram", "context_length", "expires_at", "details")
        observation["models"] = [{k: model.get(k) for k in fields} for model in payload.get("models", [])]
        expected = manifest["models"][job["model_id"]]
        matching = [m for m in observation["models"] if m.get("digest") == expected["digest"] and
                    expected["model"] in {m.get("name"), m.get("model")}]
        if matching:
            job["resident_observations"] = job.get("resident_observations", 0) + 1
            job["gpu_observed"] = job.get("gpu_observed", False) or any((m.get("size_vram") or 0) > 0 for m in matching)
            job["gpu_fully_resident_observed"] = job.get("gpu_fully_resident_observed", False) or any(
                (m.get("size") or 0) > 0 and (m.get("size_vram") or 0) >= m["size"] for m in matching)
        observation["matching_model_found"] = bool(matching)
    except ApiError as exc:
        observation["error"] = str(exc)
    path = args.output_dir / "device-observations.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(observation, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
    job["last_device_observation_at"] = observation["at"]
    manifest["device_observations"] = "device-observations.jsonl"


def recover_get(api: Api, path: str, save, manifest: dict, args: argparse.Namespace) -> dict:
    failures = 0
    while True:
        try:
            return api.request(path)
        except ApiError as exc:
            failures += 1
            manifest.setdefault("network_events", []).append({"at": now(), "path": path,
                                                               "error": str(exc)})
            save()
            if exc.status is not None or (args.network_retries and failures > args.network_retries):
                raise
            print(f"Connection interrupted ({failures}); retrying GET in {args.poll_seconds:g}s", flush=True)
            time.sleep(args.poll_seconds)


def drive_job(api: Api, manifest: dict, job: dict, args: argparse.Namespace, save) -> None:
    if job.get("status") == "exported":
        for name in ("json", "csv"):
            relative = Path(job[name])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe saved export path")
            artifact = args.output_dir / relative
            if not artifact.exists() or hashlib.sha256(artifact.read_bytes()).hexdigest() != job[name + "_file_sha256"]:
                break
        else:
            return
    if job.get("run_id") is None:
        if job.get("status") in {"creating", "creation_unknown"}:
            raise RuntimeError(f"Creation outcome unknown for {job['key']}; use --reconcile {job['key']}=run-ID")
        job.update(status="creating", creation_attempted_at=now())
        save()  # Intent is durable BEFORE the non-idempotent HTTP POST.
        print(json.dumps({"creating": job["key"], "request": job["request"],
                          "source_bank_sha256": manifest["source_bank_sha256"],
                          "model_digest": manifest["models"][job["model_id"]].get("digest"),
                          "expected_versions": manifest.get("expected_versions")}, ensure_ascii=False), flush=True)
        try:
            created = api.request("/api/v2/runs", job["request"])
            if not re.fullmatch(r"run-[a-f0-9]{12}", str(created.get("id", ""))):
                raise ApiError("Creation returned no valid run ID")
            job.update(run_id=created["id"], status="created", created_at=now())
            save()
        except ApiError as exc:
            job.update(status="rejected" if exc.status is not None and exc.status < 500 else "creation_unknown",
                       error=str(exc), last_error_at=now())
            save()
            raise
    if not re.fullmatch(r"run-[a-f0-9]{12}", job["run_id"]):
        raise ValueError("Unsafe run ID in manifest")
    run_path = "/api/v2/runs/" + job["run_id"]
    resumed_signatures: set[tuple] = set()
    while True:
        run = recover_get(api, run_path, save, manifest, args)
        assert_run_identity(run, job, manifest)
        freeze_job(run, job)
        observe_device(args, manifest, job, run)
        # A live snapshot preserves partial results even after client termination.
        local = args.output_dir / "runs" / (run["id"] + ".json")
        atomic_json(local, run)
        job["json"] = str(local.relative_to(args.output_dir)).replace("\\", "/")
        save()
        print(f"{job['key']} {run['id']} {run['status']} {run['progress']['done']}/{run['progress']['total']}", flush=True)
        if run["status"] in ACTIVE:
            time.sleep(args.poll_seconds)
            continue
        if run["status"] == "failed" and len(run["results"]) < len(run["plan"]) and not args.resume_failed:
            export_run(api, args.output_dir, run, job)
            save()
            raise RuntimeError("Platform failed before completing its plan; repair the cause, then use --resume-failed")
        if run["status"] in RESUMABLE and len(run["results"]) < len(run["plan"]):
            signature = (run["status"], len(run["results"]), len(run.get("attempts", [])))
            if signature in resumed_signatures:
                export_run(api, args.output_dir, run, job)
                save()
                raise RuntimeError("Run stopped again without progress; recorded failures are not retried")
            resumed_signatures.add(signature)
            job.setdefault("resume_requests", []).append({"at": now(), "state_before": run["status"],
                "completed_before": len(run["results"]), "status": "intent_saved"})
            save()
            try:
                api.request(run_path + "/resume", {})
                job["resume_requests"][-1]["status"] = "acknowledged"
            except ApiError as exc:
                # GET is safe after a lost resume response. Do not repeat POST here.
                job["resume_requests"][-1].update(status="response_lost", error=str(exc))
                save()
                if exc.status is not None:
                    export_run(api, args.output_dir, run, job)
                    save()
                    raise
            save()
            time.sleep(args.poll_seconds)
            continue
        export_run(api, args.output_dir, run, job)
        job.update(status="exported", final_status=run["status"],
                   complete=len(run["results"]) == len(run["plan"]),
                   errors=sum(bool(row.get("error")) for row in run["results"]))
        save()
        return


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8877")
    p.add_argument("--models", nargs="+", required=True, help="Registered platform model IDs")
    p.add_argument("--bank", required=True)
    p.add_argument("--modes", nargs="+", choices=["with_context", "no_context"], default=["with_context", "no_context"])
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--limit", type=int, help="Explicit first N selected bank-order questions; never an automatic cap")
    p.add_argument("--article-ids", nargs="+")
    p.add_argument("--question-ids", nargs="+", help="These IDs in every selected article, following bank order")
    p.add_argument("--strict-budget", choices=["auto", "true", "false"], default="auto")
    p.add_argument("--strict-time", choices=["true", "false"], default="true", help="False only for explicitly labelled historical reference/diagnostic runs")
    p.add_argument("--num-ctx", type=int, default=8192, help="Explicit window within model native limit; Yi1.5 6B uses 4096")
    p.add_argument("--strict-budget-models", nargs="*", default=[], help="Explicit certified model IDs for auto policy")
    p.add_argument("--bootstrap-repetitions", type=int, default=0, help="Platform resamples; summary CLI defaults to 2000")
    p.add_argument("--poll-seconds", type=float, default=15)
    p.add_argument("--request-timeout", type=float, default=30)
    p.add_argument("--ollama-url", help="Optional project-owned Ollama base URL for /api/ps device evidence at every poll")
    p.add_argument("--network-retries", type=int, default=20, help="Safe GET retries; 0 means unlimited")
    p.add_argument("--reconcile", action="append", default=[], metavar="MODEL__MODE=RUN-ID")
    p.add_argument("--resume-failed", action="store_true", help="Explicitly resume unfinished fatal failures after fixing the cause")
    p.add_argument("--prepare-only", action="store_true", help="Freeze plan without creating any run")
    return p


def run_matrix(args: argparse.Namespace, api: Api | None = None) -> dict:
    if len(set(args.models)) != len(args.models) or len(set(args.modes)) != len(args.modes):
        raise ValueError("Duplicate model IDs or modes")
    if not 0 < args.poll_seconds <= 30 or args.request_timeout <= 0 or args.network_retries < 0:
        raise ValueError("Poll must be >0 and <=30 seconds; timeout >0; network retries >=0")
    if not 0 <= args.bootstrap_repetitions <= 10000:
        raise ValueError("Bootstrap repetitions must be 0..10000")
    if not 1024 <= args.num_ctx <= 8192:
        raise ValueError("Context must be 1024..8192")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", args.bank):
        raise ValueError("Unsafe bank ID")
    api = api or Api(args.base_url, args.request_timeout)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "manifest.json"
    spec = {k: getattr(args, k) for k in ("bank", "models", "modes", "limit", "article_ids", "question_ids",
            "strict_budget", "strict_budget_models", "bootstrap_repetitions", "strict_time", "num_ctx")}
    manifest: dict
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        prior_spec = {"strict_time": "true", "num_ctx": 8192, **manifest["specification"]}
        if manifest.get("schema_version") != SCHEMA or prior_spec != spec:
            raise ValueError("Existing manifest has a different plan; use identical arguments or a new output directory")
    else:
        health = api.request("/api/health")
        bank = api.request("/api/v2/banks/" + args.bank)
        if bank.get("annotation_origin") == "external_public_benchmark" and args.strict_time != "false":
            raise ValueError("Historical public reference requires --strict-time false; not a time-isolated benchmark")
        model_map = {m["id"]: m for m in api.request("/api/models")["models"]}
        for mid in args.models:
            model = model_map.get(mid)
            if not model or not model.get("available") or not model.get("temporal_verified") or not model.get("digest"):
                raise ValueError(f"Model {mid} is unavailable or lacks verified historical digest/date")
            if args.num_ctx > model.get("native_context_tokens", 8192):
                raise ValueError(f"Model {mid} native context is smaller than --num-ctx")
        if set(args.strict_budget_models) - set(args.models):
            raise ValueError("--strict-budget-models contains an unselected model")
        items = selection(bank, args.article_ids, args.question_ids, args.limit)
        manifest = {"schema_version": SCHEMA, "created_at": now(), "specification": spec,
            "source_bank_sha256": bank["bank_sha256"], "source_bank_operator_snapshot": bank,
            "expected_versions": client_versions(),
            "health_at_preflight": health, "selection": items, "selection_sha256": digest(items),
            "models": {mid: model_map[mid] for mid in args.models}, "formal": False,
            "notice": "AI development questions; human review must be checked in bank snapshot. Not a formal ranking. "
                      "Strict time isolation does not prove absence of contamination. Uncertified budgets are exploratory.",
            "jobs": [{"key": mid + "__" + mode, "model_id": mid, "mode": mode, "status": "planned",
                "request": expected_request(args, mid, mode, strict_budget_for(model_map[mid], args.strict_budget,
                                                                              args.strict_budget_models))}
                for mid in args.models for mode in args.modes]}
    def save() -> None:
        manifest["updated_at"] = now()
        atomic_json(path, manifest)
    manifest.setdefault("base_url_history", [])
    if not manifest["base_url_history"] or manifest["base_url_history"][-1]["url"] != args.base_url:
        manifest["base_url_history"].append({"at": now(), "url": args.base_url})
    save()
    for value in args.reconcile:
        key, separator, run_id = value.partition("=")
        matches = [j for j in manifest["jobs"] if j["key"] == key]
        if not separator or len(matches) != 1 or not re.fullmatch(r"run-[a-f0-9]{12}", run_id):
            raise ValueError("Invalid --reconcile job key or run ID")
        job = matches[0]
        if job.get("run_id") and job["run_id"] != run_id:
            raise ValueError("Cannot replace an already frozen run ID")
        candidate = api.request("/api/v2/runs/" + run_id)
        assert_run_identity(candidate, job, manifest)
        freeze_job(candidate, job)
        job["reconciled_at"] = now()
        save()
    print(json.dumps({"manifest": str(path), "models": args.models,
        "questions_per_job": len(manifest["selection"]), "jobs": len(manifest["jobs"]),
        "planned_requests": len(manifest["selection"]) * len(manifest["jobs"]),
        "languages": {lang: sum(p["language"] == lang for p in manifest["selection"]) for lang in ("zh", "en")},
        "formal": False}, ensure_ascii=False), flush=True)
    if not args.prepare_only:
        for job in manifest["jobs"]:
            drive_job(api, manifest, job, args, save)
        manifest["finished_at"] = now()
        save()
    return manifest


def main() -> int:
    args = parser().parse_args()
    try:
        manifest = run_matrix(args)
        return int(any(j.get("errors") or j.get("final_status") == "failed" or j.get("complete") is False
                       for j in manifest["jobs"]))
    except KeyboardInterrupt:
        print("Client stopped; platform run is retained. Restart with identical arguments to continue.", file=sys.stderr)
        return 130
    except (ApiError, ValueError, RuntimeError, OSError, KeyError) as exc:
        print(f"Matrix stopped: {exc}. Existing manifest and model outputs are retained.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
