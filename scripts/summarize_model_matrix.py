"""Audit and analyze complete reading-model-matrix-v1 exports without model calls.

Example: python -m scripts.summarize_model_matrix --matrix-dirs output/matrix-a
    output/matrix-b --output-dir output/analysis-20261020

Incomplete inputs are a read-only audit: --allow-incomplete returns a progress
JSON on stdout, and deliberately creates no reports or figures. Integrity
violations are never waived. This is a development diagnostic, not a ranking.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import benchmark_v2 as scorer
from backend import experiment_v2 as runner
from scripts.run_model_matrix import SCHEMA, assert_run_identity, digest, selection

ANALYSIS_VERSION = "reading-matrix-analysis-v1.1-runner-compat-20261025"
READ_ONLY_RUNNER_VERSIONS = {"reading-runner-v2.1-attempt-log-20261013", "reading-runner-v2.2-context-reference-20261024"}
PREDECLARED_PAIRS = (("qwen25-3b", "qwen25-15b"), ("qwen25-7b", "qwen25-3b"),
                     ("qwen25-14b", "qwen25-7b"), ("qwen25-7b", "mistral03-7b"),
                     ("qwen25-7b", "internlm25-7b"),
                     # Added on provenance grounds before reading InternLM scores;
                     # retain the original registry contrast as exploratory.
                     ("qwen25-7b", "internlm25-7b-official2024"))
ANSWER_KEYS = ("choice_accuracy", "short_em", "short_token_f1", "numeric_strict_accuracy")
METRICS = (*ANSWER_KEYS, "evidence_exact_answerable", "evidence_f1_answerable",
           "correct_refusal_rate", "unanswerable_substantive_rate", "false_refusal_rate",
           "valid_output_rate", "format_error_rate", "transport_error_rate")
LOWER_BETTER = {"unanswerable_substantive_rate", "false_refusal_rate", "format_error_rate", "transport_error_rate"}
KINDS = ("all", "choice", "short", "numeric", "unanswerable")


class IntegrityError(ValueError):
    """An artifact contradicts its frozen provenance or comparison contract."""


class IncompleteError(ValueError):
    """Artifacts can be audited but are not yet a complete comparison."""


def read_json(path: Path) -> dict:
    def reject_constant(value: str) -> None:
        raise IntegrityError("Non-finite JSON constant: " + value)
    value = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise IntegrityError("Expected JSON object: " + str(path))
    return value


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained_path(directory: Path, relative: str) -> Path:
    candidate = Path(relative)
    result = (directory / candidate).resolve()
    if candidate.is_absolute() or ".." in candidate.parts or not result.is_relative_to(directory.resolve()):
        raise IntegrityError("Unsafe exported artifact path: " + relative)
    return result


def original_bank(operator_bank: dict) -> dict:
    """Undo only bank_info()'s documented operator-only decorations."""
    value = copy.deepcopy(operator_bank)
    for key in ("id", "bank_sha256", "formal_eligible", "formal_ineligible_reason", "counts", "reference_visibility"):
        value.pop(key, None)
    for article in value.get("articles", []):
        article.pop("question_count", None)
    return value


def selected_bank(source: dict, items: list[dict]) -> dict:
    value = copy.deepcopy(source)
    wanted = {(p["article_id"], p["question_id"]) for p in items}
    article_order = list(dict.fromkeys(p["article_id"] for p in items))
    index = {a["id"]: a for a in value["articles"]}
    value["articles"] = [index[aid] for aid in article_order]
    for article in value["articles"]:
        article["questions"] = [q for q in article["questions"] if (article["id"], q["id"]) in wanted]
    return value


def error_type(row: dict) -> str | None:
    error = row.get("error")
    if not error:
        return None
    text = str(error).lower()
    if text == "missing_planned_response":
        return "missing_response"
    if any(token in text for token in ("token", "预算", "截断")):
        return "budget_or_token_contract"
    if any(token in text for token in ("身份", "digest", "版本", "version")):
        return "model_or_version_identity"
    if any(token in text for token in ("timeout", "timed out", "超时", "连接", "connection", "http", "unreachable")):
        return "transport"
    if any(token in text for token in ("json", "contract", "refusal_contains", "empty_substantive", "unit", "confidence", "abstain", "evidence_ids", "响应缺少")):
        return "format_or_response_contract"
    return "other_execution"


def check_csv(path: Path, run: dict) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        actual = list(csv.DictReader(handle))
    expected_bytes, _ = runner.export_run(run, "csv")
    expected = list(csv.DictReader(io.StringIO(expected_bytes.decode("utf-8-sig"))))
    if actual != expected:
        raise IntegrityError("CSV disagrees with JSON rows/metrics/raw responses: " + str(path))


def checked_rows(run: dict) -> list[dict]:
    articles = {a["id"]: a for a in run["snapshots"]["bank"]["articles"]}
    records = {(r["article_id"], r["question_id"]): r for r in run.get("results", [])}
    attempts = run.get("attempts", [])
    if len({a["id"] for a in attempts}) != len(attempts):
        raise IntegrityError("Duplicate attempt ID")
    attempt_map = {a["id"]: a for a in attempts}
    plan_keys = {(p["model_id"], p["article_id"], p["question_id"]) for p in run["plan"]}
    for attempt in attempts:
        if (attempt.get("model_id"), attempt.get("article_id"), attempt.get("question_id")) not in plan_keys:
            raise IntegrityError("Unplanned attempt")
    rows = []
    for planned in run["plan"]:
        article = articles[planned["article_id"]]
        question = next(q for q in article["questions"] if q["id"] == planned["question_id"])
        recorded = records.get((article["id"], question["id"]))
        row = copy.deepcopy(recorded) if recorded else {**planned, "error": "missing_planned_response", "response": None}
        if recorded:
            for key, expected in (("language", article["language"]), ("kind", question["kind"]),
                                  ("dimension", question["dimension"]), ("question", question["prompt"]),
                                  ("article_sha256", article["presented_text_sha256"])):
                if row.get(key) != expected:
                    raise IntegrityError(f"Recorded row differs from frozen bank: {key}")
            attempt = attempt_map.get(row.get("attempt_id"))
            if not attempt or any(attempt.get(k) != row[k] for k in ("model_id", "article_id", "question_id", "prompt_sha256")):
                raise IntegrityError("Recorded result lacks matching durable attempt")
            wanted_status = "recorded_error" if row.get("error") else "recorded_response"
            if attempt.get("status") != wanted_status:
                raise IntegrityError("Attempt outcome contradicts recorded result")
            if not row.get("error"):
                try:
                    decoded = runner.parse_response(row["raw_response"])
                except (KeyError, ValueError) as exc:
                    raise IntegrityError("Valid result has invalid raw response") from exc
                if decoded != row.get("response"):
                    raise IntegrityError("Parsed response differs from preserved raw output")
            budget = row.get("budget", {})
            if run["config"].get("strict_budget") and not row.get("error"):
                if not budget.get("exact") or not budget.get("runtime_count_matches"):
                    raise IntegrityError("Strict successful row lacks exact runtime token agreement")
                if row.get("input_tokens") != budget.get("input_tokens"):
                    raise IntegrityError("Runtime input token count differs from frozen exact count")
            if row.get("input_tokens") is not None and (row["input_tokens"] + run["config"]["max_tokens"] +
                    budget.get("reserved_margin_tokens", 512) > run["config"]["num_ctx"] and not row.get("error")):
                raise IntegrityError("Successful result exceeded context budget")
        metrics = scorer.grade(question, row.get("response"), [p["id"] for p in article["paragraphs"]],
                               error=row.get("error"), language=article["language"])
        if run["config"]["mode"] == "no_context":
            metrics = runner._no_evidence_view(metrics)
        if recorded and row.get("metrics") != metrics:
            raise IntegrityError("Archived row metrics disagree with frozen grader version")
        row.update(language=article["language"], kind=question["kind"], dimension=question["dimension"],
                   source_cluster_id=article["source_cluster_id"], mode=run["config"]["mode"],
                   metrics=metrics, recorded=recorded is not None, run_id=run["id"], frozen_question=question,
                   article_title=article["title"], source_url=article.get("source_url"))
        row["error_type"] = error_type(row)
        rows.append(row)
    return rows


def inventory(matrix_dirs: list[Path], expected_models: list[str] | None = None,
              expected_main: int = 160, expected_no_context: int = 80,
              expected_articles_per_language: int = 10) -> dict:
    """Integrity violations always fail; missing artifacts are explicit blockers."""
    blockers, manifests, jobs, rows = [], [], {}, []
    common_source = common_versions = common_bank = None
    models: dict[str, dict] = {}
    artifacts, selected_hashes, seen_run_ids = [], {}, set()
    main_selections, control_selections = [], []
    for directory in matrix_dirs:
        path = directory / "manifest.json"
        if not path.exists():
            blockers.append("Missing manifest: " + str(path))
            continue
        manifest = read_json(path)
        if manifest.get("schema_version") != SCHEMA:
            raise IntegrityError("Unexpected matrix schema: " + str(path))
        if manifest.get("formal") is not False:
            raise IntegrityError("This CLI accepts explicitly labelled development matrices only")
        if digest(manifest["selection"]) != manifest["selection_sha256"]:
            raise IntegrityError("Manifest selection hash changed")
        source = original_bank(manifest["source_bank_operator_snapshot"])
        if digest(source) != manifest["source_bank_sha256"]:
            raise IntegrityError("Frozen source bank hash disagrees with operator snapshot")
        scorer.validate_bank(source, allow_draft=True)
        source_hash = manifest["source_bank_sha256"]
        if common_source is not None and source_hash != common_source:
            raise IntegrityError("Mixed source banks (pilot16 and main160 cannot be combined)")
        common_source, common_bank = source_hash, source
        versions = manifest.get("versions") or manifest.get("expected_versions")
        expected_versions = {"grader_version": scorer.VERSION, "prompt_version": runner.PROMPT_VERSION}
        if (not versions or set(versions) != {*expected_versions, "runner_version"}
                or any(versions.get(k) != v for k, v in expected_versions.items())
                or versions.get("runner_version") not in READ_ONLY_RUNNER_VERSIONS
                or (common_versions is not None and versions != common_versions)):
            raise IntegrityError("Runner/prompt/grader version mismatch; archived outputs cannot be silently rescored")
        common_versions = versions
        spec = manifest["specification"]
        if set(manifest["models"]) != set(spec["models"]) or not set(spec["modes"]) <= {"with_context", "no_context"}:
            raise IntegrityError("Frozen models/modes contradict matrix specification")
        selected = selection(source, spec.get("article_ids"), spec.get("question_ids"), spec.get("limit"))
        if selected != manifest["selection"]:
            raise IntegrityError("Selection does not match frozen specification/source bank")
        if len({(p["article_id"], p["question_id"]) for p in selected}) != len(selected):
            raise IntegrityError("Duplicate selected questions")
        expected_job_keys = {mid + "__" + mode for mid in spec["models"] for mode in spec["modes"]}
        if len(manifest["jobs"]) != len(expected_job_keys) or {j["key"] for j in manifest["jobs"]} != expected_job_keys:
            raise IntegrityError("Jobs differ from frozen model/mode specification")
        for mid, model in manifest["models"].items():
            if not model.get("digest"):
                raise IntegrityError("Model has no frozen digest")
            signature = {k: model.get(k) for k in ("id", "provider", "model", "digest", "release_date", "expected_digest")}
            if mid in models and models[mid]["identity"] != signature:
                raise IntegrityError("Same model ID has different frozen weights/metadata across matrices")
            models[mid] = {"identity": signature, "snapshot": model}
        manifests.append(manifest)
        artifacts.append({"path": str(path.resolve()), "sha256": sha_file(path), "kind": "matrix_manifest"})
        for job in manifest["jobs"]:
            key = (job["model_id"], job["mode"])
            if key in jobs:
                raise IntegrityError("Duplicate model/mode job across directories; repeated trials need a separate analysis")
            jobs[key] = job
            target_count = expected_main if job["mode"] == "with_context" else expected_no_context
            if len(selected) != target_count:
                raise IntegrityError(f"{job['key']} has {len(selected)} planned items, expected {target_count}; pilot jobs cannot enter the matrix")
            (main_selections if job["mode"] == "with_context" else control_selections).append(selected)
            plan_bank = selected_bank(source, selected)
            expected_hash = digest(plan_bank)
            mode = job["mode"]
            if mode in selected_hashes and selected_hashes[mode] != expected_hash:
                raise IntegrityError("Different selected question sets inside a comparison mode")
            selected_hashes[mode] = expected_hash
            if not job.get("json") or not (directory / job["json"]).exists():
                blockers.append("No saved run JSON: " + job["key"])
                continue
            run_path = contained_path(directory, job["json"])
            run = read_json(run_path)
            if run["id"] in seen_run_ids:
                raise IntegrityError("Same run ID reused across jobs")
            seen_run_ids.add(run["id"])
            try:
                assert_run_identity(run, job, copy.deepcopy(manifest))
            except (KeyError, ValueError) as exc:
                raise IntegrityError(str(exc)) from exc
            if digest(run["snapshots"]["bank"]) != expected_hash:
                raise IntegrityError("Run bank content differs from the planned projection of source bank")
            if run["id"] != job.get("run_id") or run.get("formal") is not False:
                raise IntegrityError("Run ID/formal label mismatch")
            for key, value in (("actual_config", run["config"]), ("actual_models", run["snapshots"]["models"]),
                               ("selected_bank_sha256", run["snapshots"]["bank_sha256"]),
                               ("attempts", len(run.get("attempts", [])))):
                if key in job and job[key] != value:
                    raise IntegrityError("Manifest frozen run detail contradicts export: " + key)
            if run["config"].get("allow_draft") is not True or run["config"].get("strict_time") is not True:
                raise IntegrityError("Development/time-isolation configuration changed")
            if run["config"].get("output_schema") != runner.SCHEMA or run["snapshots"].get("output_schema") != runner.SCHEMA:
                raise IntegrityError("Output schema mismatch")
            if len(run["plan"]) != target_count:
                raise IntegrityError("Unexpected plan denominator")
            if run["progress"] != {"done": len(run["results"]), "total": len(run["plan"])}:
                raise IntegrityError("Progress counters contradict plan/results")
            if job.get("json_file_sha256"):
                if sha_file(run_path) != job["json_file_sha256"]:
                    raise IntegrityError("Run JSON export hash mismatch")
            else:
                blockers.append("Run JSON not sealed by exporter: " + job["key"])
            csv_path = contained_path(directory, job["csv"]) if job.get("csv") else None
            if csv_path is None or not csv_path.exists() or not job.get("csv_file_sha256"):
                blockers.append("No sealed CSV export: " + job["key"])
            else:
                if sha_file(csv_path) != job["csv_file_sha256"]:
                    raise IntegrityError("CSV export hash mismatch")
                check_csv(csv_path, run)
                artifacts.append({"path": str(csv_path), "sha256": sha_file(csv_path), "kind": "run_csv"})
            if job.get("status") != "exported" or not job.get("complete") or len(run["results"]) != target_count or run["status"] not in {"completed", "failed"}:
                blockers.append(f"Unfinished {job['key']}: {run['status']} {len(run['results'])}/{target_count}")
            if job.get("final_status") and job["final_status"] != run["status"]:
                raise IntegrityError("Manifest terminal status contradicts run")
            if job.get("complete") is True and len(run["results"]) != len(run["plan"]):
                raise IntegrityError("Manifest falsely claims complete results")
            if "errors" in job and job["errors"] != sum(bool(r.get("error")) for r in run["results"]):
                raise IntegrityError("Manifest error count contradicts result rows")
            rows.extend(checked_rows(run))
            artifacts.append({"path": str(run_path), "sha256": sha_file(run_path), "kind": "run_json"})
        device = manifest.get("device_observations")
        if device:
            device_path = contained_path(directory, device)
            if device_path.exists():
                observations = [json.loads(line) for line in device_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                for job in manifest["jobs"]:
                    model = manifest["models"][job["model_id"]]
                    matching = [m for observed in observations if observed.get("job") == job["key"] and observed.get("run_id") == job.get("run_id")
                                for m in observed.get("models", []) if m.get("digest") == model["digest"] and model["model"] in {m.get("model"), m.get("name")}]
                    gpu_seen = any((m.get("size_vram") or 0) > 0 for m in matching)
                    full_seen = any((m.get("size") or 0) > 0 and (m.get("size_vram") or 0) >= m["size"] for m in matching)
                    if job.get("gpu_observed") and not gpu_seen or job.get("gpu_fully_resident_observed") and not full_seen:
                        raise IntegrityError("GPU residency claim lacks matching model/run device observation")
                artifacts.append({"path": str(device_path), "sha256": sha_file(device_path), "kind": "device_observations"})
            elif any(j.get("gpu_observed") or j.get("gpu_fully_resident_observed") for j in manifest["jobs"]):
                raise IntegrityError("GPU residency claim has no readable device observations")
        elif any(j.get("gpu_observed") or j.get("gpu_fully_resident_observed") for j in manifest["jobs"]):
            raise IntegrityError("GPU residency claim has no device observation artifact")
    if not common_bank:
        blockers.append("No readable matrix source bank")
    else:
        for lang in ("zh", "en"):
            source_articles = [a for a in common_bank["articles"] if a["language"] == lang]
            clusters = {a["source_cluster_id"] for a in source_articles}
            if len(source_articles) != expected_articles_per_language or len(clusters) != expected_articles_per_language:
                raise IntegrityError(f"Expected {expected_articles_per_language} independent source articles/clusters per language")
    wanted_models = expected_models or list(models)
    if set(models) - set(wanted_models):
        raise IntegrityError("Unexpected model IDs outside --expected-models")
    for model in wanted_models:
        for mode in ("with_context", "no_context"):
            if (model, mode) not in jobs:
                blockers.append(f"Missing job: {model}__{mode}")
    if main_selections and control_selections:
        main = {(p["article_id"], p["question_id"]) for p in main_selections[0]}
        control = {(p["article_id"], p["question_id"]) for p in control_selections[0]}
        if not control <= main:
            raise IntegrityError("No-context questions must be an exact paired subset of with-context questions")
    return {"analysis_version": ANALYSIS_VERSION, "formal": False, "complete": not blockers,
            "blockers": blockers, "source_bank_sha256": common_source, "bank": common_bank,
            "versions": common_versions, "models": models, "jobs": jobs, "rows": rows,
            "artifacts": artifacts, "planned_models": wanted_models,
            "progress": [{"model_id": m, "mode": mode, "planned": len([r for r in rows if r["model_id"] == m and r["mode"] == mode]),
                          "recorded": sum(r["recorded"] for r in rows if r["model_id"] == m and r["mode"] == mode),
                          "errors": sum(bool(r.get("error")) for r in rows if r["model_id"] == m and r["mode"] == mode)} for m, mode in jobs]}


def metric_value(row: dict, metric: str) -> float | None:
    known = row["kind"] != "unanswerable"
    metrics = row["metrics"]
    if metric in ANSWER_KEYS:
        return metrics.get(metric)
    if metric.startswith("evidence_"):
        if not known or row["mode"] == "no_context":
            return None
        return metrics["evidence_exact" if metric == "evidence_exact_answerable" else "evidence_f1"]
    if metric in {"correct_refusal_rate", "unanswerable_substantive_rate"}:
        return metrics["correct_refusal" if metric == "correct_refusal_rate" else "unanswerable_substantive"] if not known else None
    if metric == "false_refusal_rate":
        return metrics["false_refusal"] if known else None
    if metric == "valid_output_rate":
        return float(metrics["output_state"] != "error")
    if metric == "format_error_rate":
        return float(row["error_type"] == "format_or_response_contract")
    if metric == "transport_error_rate":
        return float(row["error_type"] == "transport")
    raise ValueError("Unknown metric: " + metric)


def quantile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * p
    low, high = math.floor(index), math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def estimate(rows: list[dict], metric: str, samples: list[list[str]]) -> dict:
    values = [metric_value(r, metric) for r in rows]
    applicable = [(r, value) for r, value in zip(rows, values) if value is not None]
    grouped = defaultdict(list)
    for row, value in applicable:
        grouped[row["source_cluster_id"]].append(value)
    boot = []
    for selected in samples:
        sampled = [value for cluster in selected for value in grouped[cluster]]
        value = mean(sampled)
        if value is not None:
            boot.append(value)
    valid = [value for row, value in applicable if row["metrics"]["output_state"] != "error"]
    per_cluster = [mean(v) for v in grouped.values() if v]
    return {"estimate": mean([v for _, v in applicable]), "numerator": sum(v for _, v in applicable),
            "denominator": len(applicable), "clusters": len(per_cluster),
            "cluster_mean_sd": statistics.stdev(per_cluster) if len(per_cluster) > 1 else None,
            "ci_lower": quantile(boot, .025), "ci_upper": quantile(boot, .975),
            "effective_resamples": len(boot), "valid_subset_estimate": mean(valid), "valid_subset_n": len(valid),
            "direction": "lower" if metric in LOWER_BETTER else "higher"}


def paired_difference(left: list[dict], right: list[dict], metric: str, samples: list[list[str]]) -> dict:
    left_map = {(r["article_id"], r["question_id"]): r for r in left}
    right_map = {(r["article_id"], r["question_id"]): r for r in right}
    if left_map.keys() != right_map.keys():
        raise IntegrityError("A paired contrast has unequal question keys")
    differences = []
    for key, row in left_map.items():
        a, b = metric_value(row, metric), metric_value(right_map[key], metric)
        if (a is None) != (b is None):
            raise IntegrityError("Paired metric applicability differs")
        if a is not None:
            differences.append((row["source_cluster_id"], a - b))
    grouped = defaultdict(list)
    for cluster, value in differences:
        grouped[cluster].append(value)
    bootstrap = []
    for selected in samples:
        value = mean([v for cluster in selected for v in grouped[cluster]])
        if value is not None:
            bootstrap.append(value)
    cluster_means = [mean(v) for v in grouped.values() if v]
    return {"difference": mean([v for _, v in differences]), "paired_items": len(differences),
            "source_clusters": len(cluster_means), "cluster_difference_sd": statistics.stdev(cluster_means) if len(cluster_means) > 1 else None,
            "ci_lower": quantile(bootstrap, .025), "ci_upper": quantile(bootstrap, .975),
            "effective_resamples": len(bootstrap), "effect_size_unit": "absolute_rate_difference; multiply by 100 for percentage points"}


def analyze(audit: dict, repetitions: int = 2000, seed: int = 20261020) -> dict:
    if not audit["complete"]:
        raise IncompleteError("Incomplete exports: no comparison bundle may be generated")
    bank, rows, model_ids = audit["bank"], audit["rows"], audit["planned_models"]
    samples = {}
    rng = random.Random(seed)
    for language in ("zh", "en"):
        clusters = sorted({a["source_cluster_id"] for a in bank["articles"] if a["language"] == language})
        samples[language] = [[rng.choice(clusters) for _ in clusters] for _ in range(repetitions)]
    numeric, errors, efficiency, wrong = [], [], [], []
    first_item_by_run = {}
    for row in rows:
        if row["recorded"]:
            first_item_by_run.setdefault(row["run_id"], (row["article_id"], row["question_id"]))
    for model_id in model_ids:
        for mode in ("with_context", "no_context"):
            for language in ("zh", "en"):
                group = [r for r in rows if (r["model_id"], r["mode"], r["language"]) == (model_id, mode, language)]
                errors.append({"model_id": model_id, "mode": mode, "language": language,
                    "planned": len(group), "recorded": sum(r["recorded"] for r in group),
                    "error_type_counts": dict(Counter(r["error_type"] for r in group if r["error_type"])),
                    "wrong_answer_valid": sum(r["metrics"]["output_state"] != "error" and not r["metrics"]["answer_correct"] for r in group),
                    "answer_correct_evidence_wrong": sum(r["kind"] != "unanswerable" and mode == "with_context" and r["metrics"]["answer_correct"] and not r["metrics"]["evidence_exact"] for r in group)})
                latencies = [r["latency_s"] for r in group if r["recorded"] and isinstance(r.get("latency_s"), (int, float))]
                input_tokens = [r["input_tokens"] for r in group if isinstance(r.get("input_tokens"), (int, float))]
                output_tokens = [r["output_tokens"] for r in group if isinstance(r.get("output_tokens"), (int, float))]
                token_pairs = [(r["output_tokens"], r["latency_s"]) for r in group if isinstance(r.get("output_tokens"), (int, float)) and (r.get("latency_s") or 0) > 0]
                warm_proxy = [r for r in group if r["recorded"] and (r["article_id"], r["question_id"]) != first_item_by_run.get(r["run_id"])]
                warm_latencies = [r["latency_s"] for r in warm_proxy if isinstance(r.get("latency_s"), (int, float))]
                warm_token_pairs = [(r["output_tokens"], r["latency_s"]) for r in warm_proxy if isinstance(r.get("output_tokens"), (int, float)) and (r.get("latency_s") or 0) > 0]
                efficiency.append({"model_id": model_id, "mode": mode, "language": language,
                    "planned": len(group), "latency_n": len(latencies), "latency_mean_s": mean(latencies),
                    "latency_median_s": quantile(latencies, .5), "latency_p95_s": quantile(latencies, .95),
                    "input_token_n": len(input_tokens), "input_tokens_mean": mean(input_tokens),
                    "output_token_n": len(output_tokens), "output_tokens_mean": mean(output_tokens),
                    "end_to_end_output_tokens_per_s": sum(t for t, _ in token_pairs) / sum(s for _, s in token_pairs) if token_pairs else None,
                    "token_throughput_effective_n": len(token_pairs),
                    "warm_proxy_excludes": "only the first recorded item of each whole run, not the first item per language; remaining rows are not guaranteed thermally/runtime stable",
                    "warm_proxy_excluded_first_items": sum(r["recorded"] for r in group) - len(warm_proxy),
                    "warm_proxy_latency_n": len(warm_latencies), "warm_proxy_latency_mean_s": mean(warm_latencies),
                    "warm_proxy_latency_median_s": quantile(warm_latencies, .5), "warm_proxy_latency_p95_s": quantile(warm_latencies, .95),
                    "warm_proxy_end_to_end_output_tokens_per_s": sum(t for t, _ in warm_token_pairs) / sum(s for _, s in warm_token_pairs) if warm_token_pairs else None,
                    "warm_proxy_throughput_n": len(warm_token_pairs),
                    "exact_budget_rows": sum(bool(r.get("budget", {}).get("exact")) for r in group),
                    "runtime_tokens_match_rows": sum(bool(r.get("budget", {}).get("runtime_count_matches")) for r in group),
                    "gpu_residency_observed": bool(audit["jobs"][(model_id, mode)].get("gpu_observed")),
                    "gpu_full_residency_observed": bool(audit["jobs"][(model_id, mode)].get("gpu_fully_resident_observed")),
                    "strict_budget": audit["jobs"][(model_id, mode)]["request"]["strict_budget"]})
                for kind in KINDS:
                    selected = group if kind == "all" else [r for r in group if r["kind"] == kind]
                    for metric in METRICS:
                        record = {"model_id": model_id, "mode": mode, "language": language,
                                  "question_kind": kind, "metric": metric, **estimate(selected, metric, samples[language])}
                        numeric.append(record)
                for row in group:
                    if row.get("error") or not row["metrics"]["answer_correct"] or (mode == "with_context" and row["kind"] != "unanswerable" and not row["metrics"]["evidence_exact"]):
                        wrong.append({k: row.get(k) for k in ("run_id", "model_id", "mode", "language", "article_id", "article_title", "source_url", "question_id", "kind", "dimension", "frozen_question", "raw_response", "response", "error", "error_type", "metrics", "latency_s", "input_tokens", "output_tokens", "attempt_id")})
    comparisons, missing_contrasts = [], []
    for a, b in PREDECLARED_PAIRS:
        if a not in model_ids or b not in model_ids:
            missing_contrasts.append({"left": a, "right": b, "reason": "Model unavailable in supplied complete matrices"})
            continue
        for language in ("zh", "en"):
            left = [r for r in rows if (r["model_id"], r["mode"], r["language"]) == (a, "with_context", language)]
            right = [r for r in rows if (r["model_id"], r["mode"], r["language"]) == (b, "with_context", language)]
            for metric in METRICS:
                comparisons.append({"comparison": "predeclared_model_contrast", "left": a, "right": b,
                    "language": language, "metric": metric, **paired_difference(left, right, metric, samples[language])})
    for model_id in model_ids:
        for language in ("zh", "en"):
            right = [r for r in rows if (r["model_id"], r["mode"], r["language"]) == (model_id, "no_context", language)]
            keys = {(r["article_id"], r["question_id"]) for r in right}
            left = [r for r in rows if (r["model_id"], r["mode"], r["language"]) == (model_id, "with_context", language) and (r["article_id"], r["question_id"]) in keys]
            for metric in ANSWER_KEYS:
                comparisons.append({"comparison": "with_context_minus_no_context_paired_subset",
                    "left": model_id + " / with_context", "right": model_id + " / no_context", "language": language,
                    "metric": metric, **paired_difference(left, right, metric, samples[language])})
    human_counts = Counter(a.get("human_review_count", 0) for a in bank["articles"])
    return {"analysis_version": ANALYSIS_VERSION, "formal": False, "source_bank_sha256": audit["source_bank_sha256"],
            "versions": audit["versions"], "source_artifacts": audit["artifacts"],
            "model_snapshots": {mid: audit["models"][mid]["snapshot"] for mid in model_ids},
            "protocol": {"unit": "source_article_cluster", "bootstrap": "language-stratified paired percentile cluster bootstrap; no domain/length sub-stratification",
                "repetitions": repetitions, "bootstrap_seed": seed, "generation_seed": 42, "generation_seeds_n": 1,
                "comparison_plan_deviation": "Five original model contrasts retained; after independent GGUF provenance checks and before inspecting InternLM scores, one official-2024 InternLM contrast/configuration was added. Registry InternLM remains an unverified-distribution exploratory reference. Different quantized tensors/tokenizer metadata do not prove retraining or contamination.",
                "temperature": 0, "confidence_level": .95, "hypothesis_tests": "none",
                "p_values": "not computed", "multiplicity": "marginal exploratory 95% CIs, not simultaneous; no significance/winner claims",
                "human_review_count_distribution": dict(human_counts), "aggregation": "planned applicable item mean; errors zero; no unified reading score",
                "valid_subset": "supplemental diagnostics only; not a replacement for end-to-end planned denominator",
                "short_f1": "project-local character/word multiset overlap, not official SQuAD/LongBench score",
                "no_context": "only exact matched questions; all evidence metrics N/A; prior knowledge difference does not prove contamination",
                "efficiency": "wall latency includes scheduling/model loading/serialization; load_duration is unavailable, so no pure decoding latency is inferred; warm_proxy excludes only each run's first recorded item, not guaranteed stable hot state; throughput is observed output tokens divided by paired end-to-end wall seconds; hardware residency is sampled, not proof every request ran on GPU"},
            "counts": {"models": len(model_ids), "articles": len(bank["articles"]), "source_clusters": len({a["source_cluster_id"] for a in bank["articles"]}),
                "questions_in_bank": sum(len(a["questions"]) for a in bank["articles"]), "model_question_rows": len(rows),
                "languages": {lang: {"articles": sum(a["language"] == lang for a in bank["articles"]), "clusters": len({a["source_cluster_id"] for a in bank["articles"] if a["language"] == lang})} for lang in ("zh", "en")}},
            "numeric_table": numeric, "paired_differences": comparisons, "missing_predeclared_contrasts": missing_contrasts,
            "errors": errors, "efficiency": efficiency, "wrong_cases": wrong}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fmt(value: float | None, percentage: bool = True) -> str:
    return "N/A" if value is None else f"{value * (100 if percentage else 1):.2f}"


def model_label(model_id: str) -> str:
    return {"qwen25-15b": "Qwen2.5 1.5B", "qwen25-3b": "Qwen2.5 3B",
            "qwen25-7b": "Qwen2.5 7B", "qwen25-14b": "Qwen2.5 14B",
            "llama31-8b": "Llama3.1 8B", "mistral03-7b": "Mistral0.3 7B",
            "internlm25-7b": "InternLM7B (registry)",
            "internlm25-7b-official2024": "InternLM7B (2024 GGUF)"}.get(model_id, model_id)


def generate_figures(bundle: dict, output_dir: Path) -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    directory = output_dir / "figures"
    directory.mkdir(exist_ok=True)
    models = list(bundle["model_snapshots"])
    colors = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#777777"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8), constrained_layout=True)
    selected_metrics = ("choice_accuracy", "short_token_f1", "numeric_strict_accuracy")
    for i, language in enumerate(("zh", "en")):
        for j, metric in enumerate(selected_metrics):
            ax = axes[i, j]
            for index, model in enumerate(models):
                row = next(r for r in bundle["numeric_table"] if (r["model_id"], r["mode"], r["language"], r["question_kind"], r["metric"]) == (model, "with_context", language, "all", metric))
                if row["estimate"] is not None:
                    ax.errorbar(index, row["estimate"] * 100,
                        yerr=[[max(0, row["estimate"] - row["ci_lower"]) * 100], [max(0, row["ci_upper"] - row["estimate"]) * 100]],
                        fmt="o", color=colors[index % len(colors)], capsize=3)
                    ax.annotate(f"n={row['denominator']}", (index, row["estimate"] * 100), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=6)
            ax.set_title(f"{language.upper()} | {metric}")
            ax.set_xticks(range(len(models)), [model_label(m) for m in models], rotation=35, ha="right")
            ax.tick_params(axis="x", labelsize=7)
            ax.set_ylim(-3, 108)
            ax.set_ylabel("Score (%)")
            ax.grid(axis="y", alpha=.2)
    fig.suptitle("Development reading diagnostics | 10 source clusters per language | 1 generation seed")
    fig.supxlabel("Source: sealed matrix run JSON/CSV; 95% marginal source-cluster bootstrap CIs; human review = 0; no ranking claim", fontsize=8)
    for suffix in ("pdf", "png"):
        fig.savefig(directory / ("figure-01-task-comparison." + suffix), dpi=200)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    for ax, language in zip(axes, ("zh", "en")):
        matrix = []
        for model in models:
            changes = {r["metric"]: r for r in bundle["paired_differences"] if r["comparison"] == "with_context_minus_no_context_paired_subset" and r["left"] == model + " / with_context" and r["language"] == language}
            matrix.append([changes[metric]["difference"] * 100 if changes[metric]["difference"] is not None else math.nan for metric in ANSWER_KEYS])
        image = ax.imshow(np.ma.masked_invalid(np.array(matrix)), cmap="BrBG", vmin=-100, vmax=100, aspect="auto")
        ax.set_xticks(range(len(ANSWER_KEYS)), ["Choice ACC", "Short EM", "Short F1", "Numeric strict"], rotation=25, ha="right")
        ax.set_yticks(range(len(models)), [model_label(m) for m in models])
        ax.set_title(language.upper() + " | with passage minus no passage")
        for i, model in enumerate(models):
            for j, metric in enumerate(ANSWER_KEYS):
                value = matrix[i][j]
                row = next(r for r in bundle["paired_differences"] if r["comparison"] == "with_context_minus_no_context_paired_subset" and r["left"] == model + " / with_context" and r["language"] == language and r["metric"] == metric)
                ax.text(j, i, "N/A" if math.isnan(value) else f"{value:+.1f}\nn={row['paired_items']}", ha="center", va="center", fontsize=8, color="white" if not math.isnan(value) and abs(value) > 65 else "black")
    fig.colorbar(image, ax=axes, label="Paired difference (percentage points)", shrink=.8)
    fig.suptitle("Context benefit on the exact paired question subset | development only")
    fig.supxlabel("Source: sealed matrix exports; missing task types = N/A; no-passage evidence is N/A; no significance tests", fontsize=8)
    for suffix in ("pdf", "png"):
        fig.savefig(directory / ("figure-02-context-difference." + suffix), dpi=200)
    plt.close(fig)
    return [{"file": str(path.relative_to(output_dir)).replace("\\", "/"), "sha256": sha_file(path)} for path in sorted(directory.iterdir()) if path.suffix in {".png", ".pdf"}]


def write_bundle(bundle: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "numeric-table.json", bundle["numeric_table"])
    with (output_dir / "numeric-table.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(bundle["numeric_table"][0]))
        writer.writeheader()
        writer.writerows(bundle["numeric_table"])
    write_json(output_dir / "paired-differences.json", bundle["paired_differences"])
    write_json(output_dir / "wrong-cases.json", bundle["wrong_cases"])
    write_json(output_dir / "error-types.json", bundle["errors"])
    write_json(output_dir / "efficiency.json", bundle["efficiency"])
    bundle["figures"] = generate_figures(bundle, output_dir)
    write_json(output_dir / "analysis.json", bundle)
    rows = [r for r in bundle["numeric_table"] if r["mode"] == "with_context" and r["question_kind"] == "all" and r["metric"] in (*ANSWER_KEYS, "evidence_exact_answerable", "evidence_f1_answerable", "correct_refusal_rate", "false_refusal_rate", "format_error_rate")]
    table = ["| 模型 | 语言 | 指标 | 估计 % | 95% 簇 bootstrap CI % | 分母 | 源文章簇 |", "|---|---|---|---:|---|---:|---:|"]
    for row in rows:
        table.append(f"| {model_label(row['model_id'])} | {row['language']} | {row['metric']} | {fmt(row['estimate'])} | [{fmt(row['ci_lower'])}, {fmt(row['ci_upper'])}] | {row['denominator']} | {row['clusters']} |")
    error_n = sum(sum(row["error_type_counts"].values()) for row in bundle["errors"])
    figure_one_observations = []
    for language in ("zh", "en"):
        observed = [r["estimate"] for r in rows if r["language"] == language and r["metric"] == "short_token_f1" and r["estimate"] is not None]
        if observed:
            figure_one_observations.append(f"{language} 短答 F1 的模型点估计范围为 {fmt(min(observed))}%—{fmt(max(observed))}%")
    figure_one_observation = "；".join(figure_one_observations) + "。" if figure_one_observations else "该题集无短答题，短答图为 N/A。"
    preferred_model = "qwen25-7b" if "qwen25-7b" in bundle["model_snapshots"] else next(iter(bundle["model_snapshots"]))
    figure_two_observations = []
    for language in ("zh", "en"):
        change = next(r for r in bundle["paired_differences"] if r["comparison"] == "with_context_minus_no_context_paired_subset" and r["left"] == preferred_model + " / with_context" and r["language"] == language and r["metric"] == "choice_accuracy")
        if change["difference"] is not None:
            figure_two_observations.append(f"{preferred_model} 的 {language} 选择题有文收益为 {fmt(change['difference'])} 个百分点（n={change['paired_items']}）")
    figure_two_observation = "；".join(figure_two_observations) + "。" if figure_two_observations else "配对子集无选择题，选择题原文收益为 N/A。"
    text = ["# 多模型阅读测评开发诊断", "", f"分析版本：`{ANALYSIS_VERSION}`。仅分析经过 hash、计划、原始输出及评分器复核的完整矩阵导出。",
        "", f"本次包含 {bundle['counts']['models']} 个固定模型配置、{bundle['counts']['articles']} 篇文章、{bundle['counts']['model_question_rows']} 条模型题目记录；中文和英文各 10 个源文章簇，生成 seed=42、temperature=0，仅一次。人工审题为 0，formal=false。",
        "", "配置身份：当同时包含两种InternLM配置时，它们属于同一基础模型的分发对照，不算两家机构或两种参数规模。registry配置未能与作者2024 GGUF认证内容等价；官方2024配置的完整文件SHA已核实。量化张量/tokenizer差异不证明重新训练或训练污染。该追加配置由独立来源核验触发，在查看InternLM得分前决定，旧结果原样保留。其他Ollama分发物虽固定digest，转换链仍未独立复现；时间门槛不等于零污染证明。",
        "", "比较问题：同系列参数规模变化、名义 7B 附近不同研发机构模型，以及相同题目的有原文与无原文差值。跨机构对比同时受到训练数据、架构、分词器、模板及量化差异影响，不能解释为研发机构单因素的因果效果。",
        "", "指标按语言、题型分别报告。选择题 ACC、短答 EM/项目自定义 token F1、严格数值正确率是答案指标；证据 EM/F1、拒答、误拒答和格式失败单独报告。没有全题合成总分，也不据此给出正式名次。",
        "", f"共发现 {error_n} 条执行或响应契约错误，全部留在计划分母并按相应成功指标记 0；完整原始错误及答错样本见 `wrong-cases.json`，错误类型见 `error-types.json`。有效输出子集只作补充诊断。",
        "", "## 精确数值表", "", *table, "", "完整题型分解、有效输出子集、分母、覆盖度和区间见 `numeric-table.csv/json`。无对应题型的值为 N/A，不能视为 0。",
        "", "## 图与解释", "", "![分题型模型诊断](figures/figure-01-task-comparison.png)", "", "目的：检查模型差异出现在哪种语言和答案任务。每点为包含错误在内的计划题均值，误差线为 2000 次源文章簇重采样的边际 95% 区间；点旁显示题数。" + figure_one_observation + "应同时查看区间和分母，不能从点估计顺序推出稳定名次。该图决定后续应优先补审哪些题型、补采哪些文章来源。",
        "", "![相同题目的原文收益](figures/figure-02-context-difference.png)", "", "目的：测量同一模型在完全相同题目上获取原文后的答案变化。格内数值是有文减无文的百分点差及配对题数；缺失题型为 N/A。" + figure_two_observation + "具体差值区间在 `paired-differences.json`；无文证据指标不适用。正差值支持模型使用了本题上下文的局部观察，不能证明模型完全没有训练污染，负差值也不单独证明记忆或题目错误。该图用于选择需要人工复查的题目与文章。",
        "", "## 允许与禁止的结论", "", "- Claim：在指定固定权重、当前开发题稿、同一生成 seed 下观察到表列任务正确率及配对差值。",
        "  - Source evidence：`analysis.json` 中的 source_artifacts、numeric_table 和 paired_differences；原文错误保存在 wrong-cases.json。",
        "  - Allowed wording：当前 20 篇开发材料上的描述性诊断；比较方向与区间见具体任务。",
        "  - Forbidden stronger wording：某模型阅读理解普遍最佳、达到正式基准水平、某公司因果优越、已排除训练污染、差异统计显著。",
        "  - Uncertainty：每语言仅 10 个簇、单 seed、人工审题 0；CI 为探索性边际区间而非同时置信带。",
        "  - Next check：双人独立审题及仲裁、扩大独立来源、运行多个 seed、冻结隐藏测试后再验证。",
        "  - Decision：weaken（保留开发诊断，禁止正式排名）。", "", "## 当前边界", "", "执行错误与不按 JSON 契约回答反映端到端平台表现；有效回答上的补充准确率不能替代完整分母。源文章簇的不确定性不等于训练随机性或跨 seed 方差。没有进行显著性检验，也没有未经多重校正的 p 值排序。时间隔离与模型 digest 固定仅减少可观察的污染风险，文章可能沿用更早知识；无原文对照不能独立鉴别污染。",
        "", "语言与材料覆盖：Llama3.1官方支持语言列表不含中文，其中文结果属探索；Mistral v0.3的中文覆盖未独立核实。中英文不是成对翻译的等难题，不能把分差解释为语言能力的因果差异。来源偏向政府/机构新闻，部分选择题干扰项较易，当前文本长度也不是模型最大长上下文压力测试。source_cluster_id为当前暂定文章簇，未完成独立人工来源谱系复核；bootstrap区间依赖这一簇定义。", "", "效率见 efficiency.json：保留全部端到端 p50/p95，时间包含模型加载、队列和序列化开销；后端没有保存 load_duration，不能解释为纯解码延迟。另列 warm_proxy，只剔除每个完整 run 的第一条记录，并不保证余下记录处于真正稳定热态；不会分别剔除每种语言的首条。GPU 常驻仅为采样观察。未严格认证 tokenizer 的模型预算属于探索性配置，精确 token 验证覆盖见表，不能自动与严格模式等同。", ""]
    (output_dir / "analysis-report.md").write_text("\n".join(text), encoding="utf-8")
    appendix = ["# 统计附录", "", json.dumps(bundle["protocol"], ensure_ascii=False, indent=2), "", "## 预定模型对比", "", "方向为 left minus right；效应量为绝对比例差，乘 100 为百分点。以下为事先指定的比较族，不通过结果挑选对比：", ""]
    appendix.extend(f"- {a} minus {b}" for a, b in PREDECLARED_PAIRS)
    appendix += ["", "所有模型对比只取 with_context；有文/无文对照先按 article_id、question_id 取相同配对子集，再计算各题型答案指标。无原文的证据、联合成功及理解总分均不纳入。", "", "抽样方案：在每种语言内，从该语言 10 个独立 source_cluster_id 有放回抽 10 个簇，每次保留簇内所有适用题；同一重采样索引用于所有模型和条件。没有把题目当成独立样本，也没有进一步按领域/长度拆成几乎均为单例的层。2000 次百分位区间为 2.5%/97.5% 分位；若某次没有适用题，该指标该次为缺失，需看 effective_resamples。", "", "报告点估计为全部计划适用题的均值；cluster_mean_sd 描述不同源文章簇的任务均值差异，并非多 seed 标准差。分母不等时，在每次样本中按抽取的适用题重新计算均值，而非把百分比当独立重复试验。", "", "显著性检验：未进行。没有参数检验，因此不作缺乏依据的正态性/方差齐性断言。不生成 p 值，不宣称胜出。列出的边际 95% CI 未作多重校正，不具备家族整体 95% 覆盖率；初始五个配对和来源核验后追加的官方InternLM配对，以及两语言多任务，均属探索性效应量。正式研究若需检验，应事前固定主指标、配对簇随机化/置换方案与 Holm 等多重校正。", "", "人工审题 0、development、formal=false。原始资料来自固定 source bank，验证过呈现正文 hash、计划键、模型 digest、运行/评分/提示版本、原始响应与解析响应、尝试日志、CSV/JSON hash 和逐行评分。外部快照 hash 一致性不独立认证文章来源真实性或人类审题身份。", "", "未完成的预定对比：", "", json.dumps(bundle["missing_predeclared_contrasts"], ensure_ascii=False, indent=2), "", "完整效应量/区间见 paired-differences.json；来源路径和 SHA256 在 analysis.json 的 source_artifacts。", ""]
    (output_dir / "stats-appendix.md").write_text("\n".join(appendix), encoding="utf-8")
    catalog = ["# 图目录", "", "所有图由真实密封矩阵导出生成，不使用示例数字；PDF 为矢量版，PNG 为预览版。模型按输入注册顺序显示，不按得分排序。", "", "## figure-01-task-comparison", "", "- 文件：figures/figure-01-task-comparison.pdf / .png。", "- 来源：numeric-table.json 中 with_context、question_kind=all 的 choice_accuracy、short_token_f1、numeric_strict_accuracy；所有原始导出及 hash 见 analysis.json。", "- 用途：比较同一开发题集上中英文各答案任务的端到端表现。", "- 图注：各语言 10 个源文章簇；每模型一次 seed=42；点旁为适用题数；误差线是 2000 次配对簇 bootstrap 的边际 95% CI；人工审题 0。", "- 观察要求：必须同时对照点估计、区间和题数；N/A 不绘点。", "- 决策作用：据题型差异选人工复查和后续补样方向；不得只凭点估计命名胜者。", "- 局限：单 seed、小簇样本、开发题稿；短答 F1 不是官方 SQuAD/LongBench 分数。", "", "## figure-02-context-difference", "", "- 文件：figures/figure-02-context-difference.pdf / .png。", "- 来源：paired-differences.json 中 comparison=with_context_minus_no_context_paired_subset。", "- 用途：检验取得原文后，在相同题目上的答案差值。", "- 图注：单位百分点，有文减无文；格内有配对题数；每语言 10 源簇；无该题型标 N/A；详细 CI 另见 JSON。", "- 观察要求：以 0 为中心读方向，不能将极小分母的极值解释为稳定效应。", "- 决策作用：负差及高无文正确率的样本优先复核提示、答案别名、知识可猜测性及早期来源。", "- 局限：无文回答可能来自推断/常识/猜测；不能把该差值视为污染检测器或因果训练诊断。", ""]
    (output_dir / "figure-catalog.md").write_text("\n".join(catalog), encoding="utf-8")
    write_json(output_dir / "bundle-manifest.json", {"analysis_version": ANALYSIS_VERSION, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "formal": False, "complete_inputs": True, "source_bank_sha256": bundle["source_bank_sha256"],
        "source_artifacts": bundle["source_artifacts"], "outputs": [{"path": str(p.relative_to(output_dir)).replace("\\", "/"), "sha256": sha_file(p)} for p in sorted(output_dir.rglob("*")) if p.is_file() and p.name != "bundle-manifest.json"]})


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix-dirs", nargs="+", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--expected-models", nargs="+", help="Declared expected model IDs; absent models block a complete report")
    p.add_argument("--expected-main-questions", type=int, default=160)
    p.add_argument("--expected-no-context-questions", type=int, default=80)
    p.add_argument("--expected-articles-per-language", type=int, default=10)
    p.add_argument("--bootstrap-repetitions", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=20261020)
    p.add_argument("--allow-incomplete", action="store_true", help="Read-only progress audit on stdout; no output reports/figures")
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if not 200 <= args.bootstrap_repetitions <= 10000:
            raise ValueError("Bootstrap repetitions must be 200..10000 (default 2000)")
        audit = inventory(args.matrix_dirs, args.expected_models, args.expected_main_questions,
                          args.expected_no_context_questions, args.expected_articles_per_language)
        if not audit["complete"]:
            print(json.dumps({k: audit[k] for k in ("analysis_version", "formal", "complete", "source_bank_sha256", "versions", "blockers", "progress")}, ensure_ascii=False, indent=2))
            if args.allow_incomplete:
                return 0
            raise IncompleteError("Matrix incomplete; only a read-only progress audit is permitted")
        bundle = analyze(audit, args.bootstrap_repetitions, args.bootstrap_seed)
        write_bundle(bundle, args.output_dir)
        print(json.dumps({"output_dir": str(args.output_dir), "formal": False, "complete": True, "counts": bundle["counts"], "figures": bundle["figures"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, KeyError, ValueError, TypeError, ImportError) as exc:
        print("Analysis stopped: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
