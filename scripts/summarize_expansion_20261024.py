"""Audit heterogeneous expansion matrices without mixing banks or contexts.

python -m scripts.summarize_expansion_20261024 --matrix-root output/expansion-20261024
    --output-dir output/analysis-expansion-20261024

Missing/incomplete jobs permit stdout-only progress with --allow-incomplete.
Integrity violations are never waived. This CLI never invokes models or edits
the frozen runs, banks, manifests or device observations it reads.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import csv
import datetime as dt
import itertools
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import benchmark_v2 as scorer, experiment_v2 as runner
from scripts.run_model_matrix import SCHEMA, assert_run_identity, client_versions, digest, selection
from scripts.summarize_model_matrix import (
    ANSWER_KEYS, KINDS, METRICS, IncompleteError, IntegrityError, check_csv,
    checked_rows, contained_path, estimate, mean, metric_value, original_bank,
    paired_difference, quantile, read_json, selected_bank, sha_file,
)

VERSION = "reading-expansion-analysis-v1-20261025"
GROUP_FIELDS = ("source_bank_sha256", "model_id", "mode", "num_ctx", "language")
EVIDENCE_KEYS = {"evidence_exact_answerable", "evidence_f1_answerable"}


def track(bank: dict) -> str:
    if bank.get("annotation_origin") == "external_public_benchmark" or bank.get("split") == "reference":
        return "public_historical_reference"
    if bank.get("synthetic") or bank.get("diagnostic_only") or any(a.get("synthetic") for a in bank["articles"]):
        return "synthetic_diagnostic"
    return "recent_development" if all(a.get("published_at", "").startswith("2026-") for a in bank["articles"]) else "development_diagnostic"


def artifact(path: Path, kind: str) -> dict:
    return {"path": str(path.resolve()), "sha256": sha_file(path), "kind": kind}


def inventory(matrix_root: Path, expected_stages: list[str] | None = None) -> dict:
    blockers, artifacts, progress = [], [], []
    banks, models, rows, jobs, seen_runs, seen_attempts = {}, {}, [], [], set(), set()
    expected_directories, manifests = {}, []
    if not matrix_root.is_dir():
        return {"complete": False, "blockers": ["Missing matrix root: " + str(matrix_root)], "progress": [], "rows": []}
    for stage in expected_stages or []:
        if not (matrix_root / (stage + "-plan.json")).is_file():
            blockers.append("Missing expected stage plan: " + stage)
    for path in sorted(matrix_root.glob("*-plan.json")):
        stage = read_json(path)
        if stage.get("schema_version") != "reading-expansion-stage-v1" or stage.get("formal") is not False:
            raise IntegrityError("Unknown/unlabelled stage plan: " + str(path))
        artifacts.append(artifact(path, "stage_plan"))
        for config in stage["configurations"]:
            directory = contained_path(matrix_root, config["name"])
            if directory in expected_directories:
                raise IntegrityError("Duplicate stage matrix name")
            expected_directories[directory] = {**config, "_stage_settings": stage.get("settings", {})}
            if not (directory / "manifest.json").exists():
                blockers.append("Missing planned matrix: " + config["name"])
    versions = client_versions()
    for path in sorted(matrix_root.rglob("manifest.json")):
        manifest = read_json(path)
        if manifest.get("schema_version") != SCHEMA:
            raise IntegrityError("Unexpected manifest in matrix root: " + str(path))
        directory = path.parent.resolve()
        if expected_directories and directory not in expected_directories:
            raise IntegrityError("Unplanned matrix inside a staged experiment: " + str(directory))
        if manifest.get("formal") is not False:
            raise IntegrityError("Explicit non-formal label is required")
        source = original_bank(manifest["source_bank_operator_snapshot"])
        source_hash = manifest["source_bank_sha256"]
        if digest(source) != source_hash or digest(manifest["selection"]) != manifest["selection_sha256"]:
            raise IntegrityError("Source bank or selection hash mismatch")
        scorer.validate_bank(source, allow_draft=True)
        if (manifest.get("versions") or manifest.get("expected_versions")) != versions:
            raise IntegrityError("Only the current expansion runner/prompt/grader versions are accepted")
        if manifest.get("expected_versions") and manifest["expected_versions"] != versions:
            raise IntegrityError("Expected versions disagree with local frozen versions")
        spec = manifest["specification"]
        if not spec.get("models") or len(set(spec["models"])) != len(spec["models"]) or set(spec["models"]) != set(manifest["models"]):
            raise IntegrityError("Model specification mismatch")
        if not spec.get("modes") or len(set(spec["modes"])) != len(spec["modes"]) or not set(spec["modes"]) <= {"with_context", "no_context"}:
            raise IntegrityError("Invalid modes")
        selected = selection(source, spec.get("article_ids"), spec.get("question_ids"), spec.get("limit"))
        if selected != manifest["selection"] or not selected:
            raise IntegrityError("Frozen selection contradicts source/specification")
        desired_keys = {mid + "__" + mode for mid in spec["models"] for mode in spec["modes"]}
        if {j["key"] for j in manifest["jobs"]} != desired_keys or len(manifest["jobs"]) != len(desired_keys):
            raise IntegrityError("Jobs contradict matrix model/mode plan")
        planned = expected_directories.get(directory)
        if planned:
            for field in ("bank", "models", "article_ids", "question_ids"):
                if spec.get(field) != planned.get(field):
                    raise IntegrityError("Matrix differs from stage plan: " + field)
            if spec["modes"] != [planned["mode"]] or spec.get("num_ctx", 8192) != planned["num_ctx"] or spec.get("strict_time", "true") != planned["strict_time"]:
                raise IntegrityError("Matrix mode/context/time differs from stage plan")
        kind = track(source)
        if kind == "public_historical_reference" and spec.get("strict_time", "true") != "false":
            raise IntegrityError("Public historical reference must not claim time isolation")
        if kind == "recent_development" and spec.get("strict_time", "true") != "true":
            raise IntegrityError("Recent development must retain declared temporal gate")
        if source_hash not in banks:
            banks[source_hash] = {"bank_id": spec["bank"], "source_bank_sha256": source_hash, "track": kind,
                "bank": source, "article_count": len(source["articles"]),
                "question_count": sum(len(a["questions"]) for a in source["articles"]),
                "human_review_counts": dict(Counter(a.get("human_review_count", 0) for a in source["articles"])),
                "evidence_interpretation": "span-derived mechanical proxy only; auxiliary" if kind == "public_historical_reference" else "AI-draft support-chain diagnostic; not human gold"}
        elif banks[source_hash]["bank_id"] != spec["bank"]:
            raise IntegrityError("Same bank content aliased to different registered bank IDs")
        for mid, model in manifest["models"].items():
            if model.get("id") != mid or not model.get("digest"):
                raise IntegrityError("Model lacks frozen identity/digest")
            signature = {k: model.get(k) for k in ("id", "provider", "model", "digest", "release_date", "expected_digest", "runtime_template_kind", "runtime_template_sha256", "tokenizer_spec")}
            if mid in models and models[mid]["signature"] != signature:
                raise IntegrityError("Model identity/template/tokenizer changed between matrices")
            models[mid] = {"signature": signature, "snapshot": model}
        artifacts.append(artifact(path, "matrix_manifest"))
        manifests.append(str(path.resolve()))
        observations = []
        if manifest.get("device_observations"):
            device_path = contained_path(directory, manifest["device_observations"])
            if device_path.exists():
                observations = [json.loads(line) for line in device_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                artifacts.append(artifact(device_path, "device_observations"))
        for job in manifest["jobs"]:
            expected_key = job["model_id"] + "__" + job["mode"]
            if job["key"] != expected_key:
                raise IntegrityError("Job identity/key mismatch")
            key = {"matrix": str(directory), "bank_id": spec["bank"], "model_id": job["model_id"],
                   "mode": job["mode"], "num_ctx": spec.get("num_ctx", 8192), "planned": len(selected)}
            state = {**key, "status": job.get("status"), "recorded": 0, "complete": False}
            progress.append(state)
            if not job.get("json"):
                blockers.append("No saved run JSON: " + expected_key + " in " + str(directory))
                continue
            run_path = contained_path(directory, job["json"])
            if not run_path.is_file():
                blockers.append("Missing run JSON: " + str(run_path))
                continue
            run = read_json(run_path)
            assert_run_identity(run, job, copy.deepcopy(manifest))
            if run["id"] in seen_runs or run["id"] != job.get("run_id") or run.get("formal") is not False:
                raise IntegrityError("Repeated/contradictory run ID or formal label")
            seen_runs.add(run["id"])
            expected_bank = selected_bank(source, selected)
            if digest(run["snapshots"]["bank"]) != digest(expected_bank):
                raise IntegrityError("Selected run bank differs from source projection")
            config = run["config"]
            if config.get("allow_draft") is not True or config.get("output_schema") != runner.SCHEMA or run["snapshots"].get("output_schema") != runner.SCHEMA:
                raise IntegrityError("Draft/output schema configuration mismatch")
            if config.get("num_ctx") != spec.get("num_ctx", 8192) or config.get("strict_time") != (spec.get("strict_time", "true") == "true"):
                raise IntegrityError("Context/time specification does not match run")
            native = run["snapshots"]["models"][0].get("native_context_tokens")
            if native is not None and (type(native) is not int or config["num_ctx"] > native):
                raise IntegrityError("Frozen run exceeds the model's declared native context")
            if config.get("temperature") != 0 or config.get("seed") != 42 or config.get("max_tokens") != 512:
                raise IntegrityError("Generation settings changed")
            if planned and any(config.get(field) != value for field, value in planned["_stage_settings"].items()):
                raise IntegrityError("Run settings differ from the frozen stage plan")
            if run["progress"] != {"done": len(run["results"]), "total": len(run["plan"])}:
                raise IntegrityError("Plan/progress/result counts disagree")
            for field, value in (("actual_config", config), ("actual_models", run["snapshots"]["models"]),
                                 ("selected_bank_sha256", run["snapshots"]["bank_sha256"]), ("attempts", len(run["attempts"]))):
                if field in job and job[field] != value:
                    raise IntegrityError("Frozen job detail disagrees: " + field)
            if job.get("json_file_sha256"):
                if sha_file(run_path) != job["json_file_sha256"]:
                    raise IntegrityError("Run JSON export hash mismatch")
            else:
                blockers.append("Unsealed JSON export: " + str(run_path))
            if not job.get("csv"):
                blockers.append("Missing CSV export: " + expected_key)
            else:
                csv_path = contained_path(directory, job["csv"])
                if not csv_path.is_file() or not job.get("csv_file_sha256"):
                    blockers.append("Unsealed/missing CSV export: " + str(csv_path))
                else:
                    if sha_file(csv_path) != job["csv_file_sha256"]:
                        raise IntegrityError("CSV export hash mismatch")
                    check_csv(csv_path, run)
                    artifacts.append(artifact(csv_path, "run_csv"))
            complete = (job.get("status") == "exported" and job.get("complete") is True and
                        run["status"] == "completed" and len(run["results"]) == len(run["plan"]))
            if not complete:
                blockers.append("Unfinished/failed job: " + expected_key + " in " + str(directory))
            if job.get("complete") is True and len(run["results"]) != len(run["plan"]):
                raise IntegrityError("Job falsely claims complete responses")
            if job.get("final_status") and job["final_status"] != run["status"]:
                raise IntegrityError("Final run status mismatch")
            if "errors" in job and job["errors"] != sum(bool(r.get("error")) for r in run["results"]):
                raise IntegrityError("Error count mismatch")
            for attempt in run["attempts"]:
                if attempt["id"] in seen_attempts:
                    raise IntegrityError("Attempt ID repeated across runs")
                seen_attempts.add(attempt["id"])
            checked = checked_rows(run)
            for row in checked:
                if row["recorded"] and not isinstance(row.get("raw_response"), str):
                    raise IntegrityError("Recorded result has no preserved raw-response string")
                row.update(source_bank_sha256=source_hash, bank_id=spec["bank"], bank_track=kind,
                           num_ctx=config["num_ctx"], strict_time=config["strict_time"],
                           strict_budget=config["strict_budget"], matrix=str(directory))
            rows.extend(checked)
            model = manifest["models"][job["model_id"]]
            matching = [m for o in observations if o.get("job") == expected_key and o.get("run_id") == run["id"]
                        for m in o.get("models", []) if m.get("digest") == model["digest"] and model["model"] in {m.get("name"), m.get("model")}]
            gpu = any((m.get("size_vram") or 0) > 0 for m in matching)
            full = any((m.get("size") or 0) > 0 and (m.get("size_vram") or 0) >= m["size"] for m in matching)
            if job.get("gpu_observed") and not gpu or job.get("gpu_fully_resident_observed") and not full:
                raise IntegrityError("GPU residency claim lacks matching observation")
            state.update(recorded=len(run["results"]), run_status=run["status"], complete=complete, run_id=run["id"], errors=sum(bool(r.get("error")) for r in run["results"]))
            jobs.append({**key, "run_id": run["id"], "attempts": len(run["attempts"]), "selection_sha256": manifest["selection_sha256"],
                         "json": str(run_path), "gpu_observed": gpu, "gpu_fully_resident_observed": full,
                         "strict_budget": config["strict_budget"], "strict_time": config["strict_time"],
                         "temperature": config["temperature"], "seed": config["seed"], "max_tokens": config["max_tokens"]})
            artifacts.append(artifact(run_path, "run_json"))
    if not manifests:
        blockers.append("No matrix manifests found")
    item_keys = [tuple(row[k] for k in (*GROUP_FIELDS, "article_id", "question_id")) for row in rows]
    if len(item_keys) != len(set(item_keys)):
        raise IntegrityError("Repeated question in the same bank/model/mode/context; cannot treat repeat as independent data")
    return {"analysis_version": VERSION, "formal": False, "complete": not blockers, "blockers": blockers,
            "progress": progress, "banks": banks, "models": models, "rows": rows, "jobs": jobs,
            "source_artifacts": artifacts, "versions": versions,
            "counts": {"matrix_manifests": len(manifests), "banks": len(banks), "models": len(models),
                       "runs": len(seen_runs), "attempts": len(seen_attempts), "planned_rows": len(rows),
                       "recorded_rows": sum(r["recorded"] for r in rows), "response_errors": sum(bool(r.get("error")) for r in rows)}}


def group_record(key: tuple, banks: dict) -> dict:
    record = dict(zip(GROUP_FIELDS, key))
    bank = banks[record["source_bank_sha256"]]
    return {**record, "bank_id": bank["bank_id"], "bank_track": bank["track"]}


def analyze(audit: dict, repetitions: int = 2000, seed: int = 20261025) -> dict:
    if not audit["complete"]:
        raise IncompleteError("Complete, sealed successful run exports are required for analysis")
    groups = defaultdict(list)
    for row in audit["rows"]:
        groups[tuple(row[k] for k in GROUP_FIELDS)].append(row)
    sample_cache = {}

    def samples(bank_hash: str, language: str, rows: list[dict]) -> list[list[str]]:
        clusters = tuple(sorted({r["source_cluster_id"] for r in rows}))
        cache_key = (bank_hash, language, clusters)
        if cache_key not in sample_cache:
            fixed_seed = seed + int(digest(list(cache_key))[:16], 16)
            rng = random.Random(fixed_seed)
            sample_cache[cache_key] = [[rng.choice(clusters) for _ in clusters] for _ in range(repetitions)] if len(clusters) >= 2 else []
        return sample_cache[cache_key]

    numeric, errors, cases, efficiency, coverage = [], [], [], [], []
    for key, rows in sorted(groups.items()):
        identity = group_record(key, audit["banks"])
        is_reference = identity["bank_track"] == "public_historical_reference"
        resamples = samples(key[0], key[-1], rows)
        clusters = len({r["source_cluster_id"] for r in rows})
        coverage.append({**identity, "planned_questions": len(rows), "recorded_questions": sum(r["recorded"] for r in rows),
                         "selected_articles": len({r["article_id"] for r in rows}), "selected_source_clusters": clusters,
                         "question_kind_counts": dict(Counter(r["kind"] for r in rows)),
                         "dimension_counts": dict(Counter(r["dimension"] for r in rows)),
                         "run_ids": sorted({r["run_id"] for r in rows}),
                         "strict_time": sorted({r["strict_time"] for r in rows}),
                         "strict_budget": sorted({r["strict_budget"] for r in rows})})
        for kind in KINDS:
            subset = rows if kind == "all" else [r for r in rows if r["kind"] == kind]
            for metric in METRICS:
                proxy = is_reference and metric in EVIDENCE_KEYS
                output_metric = ("span_proxy_evidence_em_aux" if metric == "evidence_exact_answerable" else "span_proxy_evidence_f1_aux") if proxy else metric
                numeric.append({**identity, "question_kind": kind, "metric": output_metric, "metric_key": metric,
                    "metric_role": "auxiliary_span_proxy" if proxy else "development_task_diagnostic",
                    **estimate(subset, metric, resamples),
                    "ci_status": "exploratory_cluster_percentile" if clusters >= 2 else "not_estimated_fewer_than_two_clusters"})
        error_counts = Counter(r["error_type"] for r in rows if r.get("error_type"))
        errors.append({**identity, "planned": len(rows), "errors": sum(error_counts.values()),
                       "error_type_counts": dict(error_counts),
                       "wrong_answer_valid": sum(not r.get("error") and not r["metrics"]["answer_correct"] for r in rows)})
        latencies = [r["latency_s"] for r in rows if isinstance(r.get("latency_s"), (int, float)) and math.isfinite(r["latency_s"]) and r["latency_s"] >= 0]
        tokens = [(r["output_tokens"], r["latency_s"]) for r in rows if isinstance(r.get("output_tokens"), int) and r["output_tokens"] >= 0 and isinstance(r.get("latency_s"), (int, float)) and r["latency_s"] > 0]
        efficiency.append({**identity, "planned": len(rows), "latency_n": len(latencies), "latency_mean_s": mean(latencies),
            "latency_p50_s": quantile(latencies, .5), "latency_p95_s": quantile(latencies, .95),
            "observed_output_tokens_per_end_to_end_second": sum(t for t, _ in tokens) / sum(s for _, s in tokens) if tokens else None,
            "token_throughput_effective_n": len(tokens), "exact_budget_rows": sum(bool(r.get("budget", {}).get("exact")) for r in rows),
            "runtime_token_agreement_rows": sum(bool(r.get("budget", {}).get("runtime_count_matches")) for r in rows),
            "timing_note": "Includes cold loading, scheduling and serialization; not pure decoding speed."})
        for row in rows:
            reason = []
            if row.get("error"):
                reason.append("response_error")
            if not row["metrics"]["answer_correct"]:
                reason.append("answer_not_correct")
            if row["mode"] == "with_context" and row["kind"] != "unanswerable" and not row["metrics"]["evidence_exact"]:
                reason.append("span_proxy_evidence_mismatch_aux" if is_reference else "AI_draft_evidence_mismatch")
            if reason:
                cases.append({**identity, "case_reasons": reason, **{k: row.get(k) for k in (
                    "run_id", "article_id", "article_title", "source_cluster_id", "source_url", "question_id", "kind", "dimension",
                    "frozen_question", "raw_response", "response", "error", "error_type", "metrics", "attempt_id", "latency_s")}})

    paired, unavailable_pairs = [], []

    def contrast(left_key: tuple, right_key: tuple, comparison: str, metrics: tuple) -> None:
        left, right = groups[left_key], groups[right_key]
        # All grouping keys include bank canonical, and no cross-bank contrast
        # is permitted even if article/question IDs happen to coincide.
        if left_key[0] != right_key[0] or left_key[-1] != right_key[-1]:
            raise IntegrityError("Cross-bank/language pairing is forbidden")
        left_map = {(r["article_id"], r["question_id"]): r for r in left}
        right_map = {(r["article_id"], r["question_id"]): r for r in right}
        common = sorted(left_map.keys() & right_map.keys())
        info = {"comparison": comparison, "source_bank_sha256": left_key[0],
                "bank_id": audit["banks"][left_key[0]]["bank_id"], "bank_track": audit["banks"][left_key[0]]["track"],
                "language": left_key[-1], "left_model": left_key[1], "right_model": right_key[1],
                "left_mode": left_key[2], "right_mode": right_key[2], "left_num_ctx": left_key[3], "right_num_ctx": right_key[3],
                "left_total_questions": len(left), "right_total_questions": len(right), "matched_questions": len(common),
                "excluded_left_questions": len(left_map.keys() - right_map.keys()),
                "excluded_right_questions": len(right_map.keys() - left_map.keys()),
                "comparison_status": "exploratory; same-bank exact-question intersection only; no significance test"}
        if not common:
            unavailable_pairs.append({**info, "reason": "No identical questions; means are never subtracted"})
            return
        left_paired, right_paired = [left_map[k] for k in common], [right_map[k] for k in common]
        resamples = samples(left_key[0], left_key[-1], left_paired)
        for metric in metrics:
            proxy = info["bank_track"] == "public_historical_reference" and metric in EVIDENCE_KEYS
            output_metric = ("span_proxy_evidence_em_aux" if metric == "evidence_exact_answerable" else "span_proxy_evidence_f1_aux") if proxy else metric
            paired.append({**info, "metric": output_metric, "metric_key": metric,
                           "metric_role": "auxiliary_span_proxy" if proxy else "development_task_diagnostic",
                           **paired_difference(left_paired, right_paired, metric, resamples)})

    keys = sorted(groups)
    for left, right in itertools.combinations(keys, 2):
        if left[0] != right[0] or left[-1] != right[-1]:
            continue
        same_model, same_mode, same_context = left[1] == right[1], left[2] == right[2], left[3] == right[3]
        if same_model and same_context and not same_mode:
            with_key = left if left[2] == "with_context" else right
            no_key = right if with_key == left else left
            contrast(with_key, no_key, "with_context_minus_no_context_exact_subset", ANSWER_KEYS)
        elif same_model and same_mode and not same_context:
            larger, smaller = (left, right) if left[3] > right[3] else (right, left)
            contrast(larger, smaller, "larger_minus_smaller_context_exact_subset", ANSWER_KEYS)
        elif not same_model and same_context and same_mode and left[2] == "with_context":
            contrast(left, right, "model_difference_exact_subset_exploratory", METRICS)
    bank_metadata = {key: {k: v for k, v in value.items() if k != "bank"} for key, value in audit["banks"].items()}
    return {"analysis_version": VERSION, "formal": False, "complete_inputs": True,
            "counts": audit["counts"], "versions": audit["versions"], "banks": bank_metadata,
            "model_snapshots": {k: v["snapshot"] for k, v in audit["models"].items()},
            "jobs": audit["jobs"], "source_artifacts": audit["source_artifacts"], "coverage": coverage,
            "numeric_table": numeric, "paired_differences": paired, "unavailable_pairs": unavailable_pairs,
            "errors": errors, "wrong_cases": cases, "efficiency": efficiency,
            "protocol": {"group_by": list(GROUP_FIELDS), "bootstrap_repetitions": repetitions,
                "bootstrap_seed": seed, "confidence_level": .95, "generation_seed": 42, "generation_seeds_n": 1,
                "bootstrap_unit": "source_cluster_id within bank/language and actual selected cohort; whole clusters resampled",
                "pairing": "same canonical bank, language and identical article/question keys; intersection only",
                "context_policy": "Never subtract 4K-subset and 8K-full means; report paired intersection with excluded counts",
                "metrics": "Project-local normalization/character-word F1; not official SQuAD/CMRC leaderboard scores",
                "public_reference_evidence": "span-derived proxy, auxiliary only; no genuine reasoning-chain accuracy claim",
                "aggregation": "all planned applicable questions; errors zero; valid subset diagnostic only; missing task N/A",
                "statistics": "exploratory marginal percentile 95% cluster CIs; no tests, p values, multiplicity/winner claims",
                "small_cluster_policy": "fewer than two clusters: CI not estimated; degenerate finite-sample CI is not certainty",
                "limitations": "human review 0; public historical training contamination high/unknown; recent dates do not prove no contamination; provisional clusters; single seed"}}


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def table_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def figures(bundle: dict, directory: Path) -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    target = directory / "figures"
    target.mkdir(exist_ok=True)
    generated = []
    tasks = ("choice_accuracy", "short_em", "short_token_f1", "numeric_strict_accuracy")
    headings = ("Choice ACC", "Short EM", "Short F1", "Numeric strict")
    selected = [r for r in bundle["numeric_table"] if r["mode"] == "with_context" and r["question_kind"] == "all" and r["metric_key"] in tasks]
    facets = sorted({(r["source_bank_sha256"], r["num_ctx"], r["language"]) for r in selected})
    if facets:
        fig, axes = plt.subplots(math.ceil(len(facets) / 2), 2, figsize=(14, 3.3 * math.ceil(len(facets) / 2)), squeeze=False, constrained_layout=True)
        for axis, facet in zip(axes.flat, facets):
            group = [r for r in selected if (r["source_bank_sha256"], r["num_ctx"], r["language"]) == facet]
            models = sorted({r["model_id"] for r in group})
            mapping = {(r["model_id"], r["metric_key"]): r for r in group}
            matrix = np.array([[100 * mapping[(m, metric)]["estimate"] if mapping[(m, metric)]["estimate"] is not None else np.nan for metric in tasks] for m in models])
            cmap = plt.colormaps["Blues"].copy(); cmap.set_bad("#eeeeee")
            axis.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="auto")
            axis.set_xticks(range(4), headings, fontsize=9)
            axis.set_yticks(range(len(models)), models, fontsize=9)
            name = bundle["banks"][facet[0]]["bank_id"]
            axis.set_title(f"{name}\nctx={facet[1]} | {facet[2]} | separate cohort", fontsize=10)
            for i, m in enumerate(models):
                for j, metric in enumerate(tasks):
                    row = mapping[(m, metric)]
                    value = matrix[i, j]
                    axis.text(j, i, "N/A" if np.isnan(value) else f"{value:.1f}%\nn={row['denominator']}", ha="center", va="center", fontsize=9,
                              color="white" if not np.isnan(value) and value > 65 else "black")
        for axis in list(axes.flat)[len(facets):]:
            axis.set_visible(False)
        fig.suptitle("Separate-bank task diagnostics | no pooled reading score | human review 0", fontsize=13)
        fig.supxlabel("All planned failures retained; project-local scores, not official benchmark leaderboard metrics", fontsize=8)
        for extension in ("png", "pdf"):
            path = target / ("figure-01-bank-task-comparison." + extension)
            fig.savefig(path, dpi=180)
            generated.append(path)
        plt.close(fig)
    paired = [r for r in bundle["paired_differences"] if r["comparison"] == "with_context_minus_no_context_exact_subset" and r["left_num_ctx"] == 4096]
    facets = sorted({(r["source_bank_sha256"], r["language"]) for r in paired})
    if facets:
        fig, axes = plt.subplots(1, len(facets), figsize=(7 * len(facets), 4.6), squeeze=False, constrained_layout=True)
        for axis, facet in zip(axes.flat, facets):
            group = [r for r in paired if (r["source_bank_sha256"], r["language"]) == facet]
            models = sorted({r["left_model"] for r in group})
            mapping = {(r["left_model"], r["metric_key"]): r for r in group}
            matrix = np.array([[100 * mapping[(m, metric)]["difference"] if mapping[(m, metric)]["difference"] is not None else np.nan for metric in tasks] for m in models])
            cmap = plt.colormaps["BrBG"].copy(); cmap.set_bad("#eeeeee")
            axis.imshow(matrix, cmap=cmap, vmin=-100, vmax=100, aspect="auto")
            axis.set_xticks(range(4), headings, fontsize=9, rotation=15)
            axis.set_yticks(range(len(models)), models, fontsize=9)
            axis.set_title(f"{bundle['banks'][facet[0]]['bank_id']}\n4096 context | {facet[1]} | with minus without", fontsize=10)
            for i, m in enumerate(models):
                for j, metric in enumerate(tasks):
                    row, value = mapping[(m, metric)], matrix[i, j]
                    axis.text(j, i, "N/A" if np.isnan(value) else f"{value:+.1f} pp\nn={row['paired_items']}", ha="center", va="center", fontsize=9,
                              color="white" if not np.isnan(value) and abs(value) > 65 else "black")
        fig.suptitle("4K same-question context benefit | descriptive, not a contamination detector", fontsize=13)
        fig.supxlabel("Only identical questions are paired; CIs are in paired-differences.json; evidence is not applicable without context", fontsize=8)
        for extension in ("png", "pdf"):
            path = target / ("figure-02-four-k-context-difference." + extension)
            fig.savefig(path, dpi=180)
            generated.append(path)
        plt.close(fig)
    return [{"file": p.relative_to(directory).as_posix(), "sha256": sha_file(p)} for p in sorted(generated)]


def write_bundle(bundle: dict, output: Path, skip_figures: bool = False) -> None:
    if output.exists() and any(output.iterdir()):
        metadata_path = output / "metadata.json"
        if not metadata_path.is_file() or not (output / "bundle-manifest.json").is_file():
            raise IntegrityError("Output directory contains unsealed files; choose a new directory")
        previous = read_json(metadata_path)
        previous_skip = previous.get("figure_policy", "").startswith("explicit --skip-figures")
        if (previous.get("source_artifacts") != bundle["source_artifacts"] or
                previous.get("protocol") != bundle["protocol"] or previous_skip != skip_figures):
            raise IntegrityError("Output is already sealed for other inputs/options; choose a new output directory")
    if not skip_figures:
        # Fail before producing a partial report when the chosen Python has no
        # plotting runtime. Use the bundled analysis Python, not inference venv.
        import matplotlib  # noqa: F401
        import numpy  # noqa: F401
    output.mkdir(parents=True, exist_ok=True)
    for filename, key in (("numeric-table", "numeric_table"), ("paired-differences", "paired_differences"),
                          ("wrong-cases", "wrong_cases"), ("error-types", "errors"), ("efficiency", "efficiency")):
        write_json(output / (filename + ".json"), bundle[key])
    table_csv(output / "numeric-table.csv", bundle["numeric_table"])
    table_csv(output / "paired-differences.csv", bundle["paired_differences"])
    bundle["figures"] = [] if skip_figures else figures(bundle, output)
    bundle["figure_policy"] = "explicit --skip-figures; no figures generated" if skip_figures else "real audited numeric values only; unavailable pair panels omitted"
    metadata = {k: bundle[k] for k in ("analysis_version", "formal", "complete_inputs", "counts", "versions", "banks", "model_snapshots", "jobs", "coverage", "source_artifacts", "protocol", "unavailable_pairs", "figure_policy")}
    metadata["analysis_source"] = artifact(Path(__file__), "analysis_code")
    write_json(output / "metadata.json", metadata)
    write_json(output / "analysis.json", bundle)
    show_metrics = {*ANSWER_KEYS, "correct_refusal_rate", "format_error_rate"}
    rows = [r for r in bundle["numeric_table"] if r["question_kind"] == "all" and r["mode"] == "with_context" and r["metric_key"] in show_metrics]
    table = ["| 题库（canonical分组） | 窗口 | 模型 | 语言 | 指标 | 估计% | 适用题数 | 来源簇 | 95% CI% |", "|---|---:|---|---|---|---:|---:|---:|---|"]

    def fmt(value: float | None) -> str:
        return "N/A" if value is None else f"{value * 100:.2f}"

    for row in rows:
        interval = "N/A" if row["ci_lower"] is None else f"[{fmt(row['ci_lower'])}, {fmt(row['ci_upper'])}]"
        table.append(f"| {row['bank_id']} | {row['num_ctx']} | {row['model_id']} | {row['language']} | {row['metric']} | {fmt(row['estimate'])} | {row['denominator']} | {row['clusters']} | {interval} |")
    report = ["# 扩展模型与异质题库：可审计开发诊断", "",
              f"分析版本`{VERSION}`。本报告只描述所提供目录中完成、封存且复核通过的矩阵；不推断尚未启动的其他实验。", "",
              f"核验 {bundle['counts']['matrix_manifests']} 份矩阵、{bundle['counts']['runs']} 个run、{bundle['counts']['recorded_rows']} 条模型题目记录、{bundle['counts']['attempts']} 个全局唯一attempt。{bundle['counts']['response_errors']} 条响应错误保留于计划分母，不删除、不自动重试。", "",
              "## 数据与比较边界", "", "每个source bank canonical、模型、mode、num_ctx和语言分别报告。近期AI题稿、公开历史参考及合成诊断不合并总分或文章数量；公开数据的passage不自动等于独立上游文章。单语言题库只报告实际语言，缺题型为N/A。metadata.json给完整bank身份、覆盖、来源簇与每run配置。", "",
              "公开SQuAD/CMRC参考可能被训练见过，关闭不适用的时间隔离；答案使用原公开标注，但本项目人审为0。短答F1/EM按本项目规范化，不能当作官方榜单分数。其evidence只由answer span派生，数值表以span_proxy_*_aux单列，不能解释为真实推理证据定位。", "",
              "4K子集和8K全量的均值不可直接相减。全部有/无文、模型以及窗口差值只在相同canonical、相同语言、完全相同article/question交集上计算；paired-differences.json列两侧全量、匹配题数和被排除数量。自动枚举的模型对比均为探索性，不冒充原始预注册。", "",
              "## 有原文任务结果", "", *table, "",
              "完整题型分解、有效输出子集、证据/拒答/错误指标见numeric-table.csv/json。有效输出子集只辅助诊断，不能替代包含失败的计划分母。无文条件不评分证据。实质误答率和误拒答率在无效响应上也记0，其低值不能单独说明可靠或少幻觉。", "",
              "## 图与解释", ""]
    catalog = ["# 图目录", "", "所有图均来自已核验的真实导出；不填充虚构数字；PNG预览、PDF矢量版本。", ""]
    for number, (stem, title, interpretation) in enumerate((
        ("figure-01-bank-task-comparison", "各bank/窗口/语言的任务表现", "各面板独立显示题型点估计和适用题数。N/A表示未覆盖；面板材料不同，颜色或数值不能直接作跨bank/窗口能力排序。该图用于识别任务覆盖和待复核的错误方向；详细CI在数值表。"),
        ("figure-02-four-k-context-difference", "4K条件下相同题目的有文收益", "差值为有文减无文，单位百分点，并列配对题数。只使用同一bank、模型、4K窗口下的同题交集；原始8K全量没有直接参与相减。正差支持本子集取得文本后有帮助，不能证明训练无污染或纯理解增益。")
    ), 1):
        png = f"figures/{stem}.png"
        if any(f["file"] == png for f in bundle["figures"]):
            report += [f"![{title}]({png})", "", interpretation, ""]
            catalog += [f"## 图{number}：{title}", "", f"- 文件：{png}及同名PDF。", f"- 解读：{interpretation}", "- 来源：numeric-table.json或paired-differences.json；上游导出及hash见metadata.json。", "- 局限：单seed、人审0、来源簇暂定、小样本/高分CI可退化；无显著性或赢家声明。", ""]
        else:
            report += [f"{title}：未生成（显式跳过绘图或尚无适用配对），不以示例数据替代。", ""]
    report += ["## 失败与复现", "", "wrong-cases.json保留答案错误、输出错误及证据不匹配的原始响应/金标。公开参考的证据不匹配明确标aux。error-types.json与efficiency.json分组记录错误和端到端耗时；耗时含加载、调度、序列化，不能当纯解码速度。GPU驻留只为采样观察；缺少对应观察不会被写成已证明GPU执行。", "",
               "metadata.json、bundle-manifest.json记录题库身份、选择、模型digest、版本及上游/产物hash。所有统计限于这批完整输入；与10月20日不同runner的历史8配置不得混合重采样。正式隐藏集、双人独立审题和多seed实验仍未因此完成。", ""]
    (output / "analysis-report.md").write_text("\n".join(report), encoding="utf-8")
    appendix = ["# 统计附录", "", json.dumps(bundle["protocol"], ensure_ascii=False, indent=2), "",
                "## 抽样、分母与配对", "", "每个bank、语言和实际选中来源簇集合使用固定种子，按source_cluster_id有放回抽取同样数量的簇，簇内适用题全保留。不同模型同一簇集合使用相同重采样索引；差值在精确同题交集上成对计算，重采样仅使用这些共同题的来源簇。没有把同篇多题当作独立重复。", "",
                "比例/F1点估计按全部计划适用题求均值，失败记0；kind缺失分母0、值为N/A。每次bootstrap按抽到的全部适用题重新求均值，2.5%/97.5%分位构成探索性边际区间；effective_resamples记录有适用值的次数。若少于2个来源簇不估CI。cluster_mean_sd/cluster_difference_sd是来源簇差异，不是跨seed标准差。", "",
                "CI不作多重校正、不具备家族整体95%覆盖；不计算p值、不声称显著或赢家。全对等有限样本可能产生退化区间，不代表总体不确定性为0。只有一次生成seed=42，公开参考训练污染高/未知，近期稿人审0；来源簇未经完整人工谱系复核。", "",
                "所有模型对比是完整已提供分组的探索性枚举，不是新的预注册。窗口比较方向为较大窗口减较小窗口，且先取相同题交集；不同canonical bank绝不配对。某配置缺少无文/另一模型不自动补0；没有共同题则写unavailable_pairs，不直接减均值。", "",
                "## 审计规则", "", "只接受当前v2.2 runner及当前prompt/grader版本。逐矩阵核对stage计划（存在时）、source bank/selection canonical hash、完整model/mode作业、配置快照、模型digest/模板/分词身份、原题计划、全局run/attempt唯一、导出JSON/CSV SHA、CSV重建一致、原始有效响应解析及逐行重评分。全部job须completed+exported+complete；failed即使已填满也不视作完成。GPU声明必须有匹配run/model digest的设备观察。", "",
                "来源hash验证只能证明快照一致，不证明网页真实性、全球最早发表、独立人审或训练非成员身份。归档输出和当前版本无条件等价也不因hash而成立。", ""]
    (output / "stats-appendix.md").write_text("\n".join(appendix), encoding="utf-8")
    (output / "figure-catalog.md").write_text("\n".join(catalog), encoding="utf-8")
    write_json(output / "bundle-manifest.json", {"analysis_version": VERSION, "formal": False,
        "complete_inputs": True, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "counts": bundle["counts"], "source_artifacts": bundle["source_artifacts"],
        "outputs": [{"path": p.relative_to(output).as_posix(), "sha256": sha_file(p)}
                    for p in sorted(output.rglob("*")) if p.is_file() and p.name != "bundle-manifest.json"]})


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--expected-stages", nargs="*", default=[], help="Require these stage plan files as well as all configurations in present plans")
    p.add_argument("--bootstrap-repetitions", type=int, default=2000)
    p.add_argument("--bootstrap-seed", type=int, default=20261025)
    p.add_argument("--allow-incomplete", action="store_true", help="Incomplete: stdout progress only, no reports/plots/directories")
    p.add_argument("--skip-figures", action="store_true", help="Explicit text/table-only bundle; no fake figures")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if not 200 <= args.bootstrap_repetitions <= 10000:
            raise ValueError("Bootstrap repetitions must be 200..10000")
        audit = inventory(args.matrix_root, args.expected_stages)
        if not audit["complete"]:
            print(json.dumps({k: audit[k] for k in ("complete", "blockers", "progress")}, ensure_ascii=False, indent=2))
            if args.allow_incomplete:
                return 0
            raise IncompleteError("Expansion incomplete; no analysis bundle was created")
        bundle = analyze(audit, args.bootstrap_repetitions, args.bootstrap_seed)
        write_bundle(bundle, args.output_dir, args.skip_figures)
        print(json.dumps({"complete": True, "formal": False, "output_dir": str(args.output_dir),
                          "counts": bundle["counts"], "figures": bundle["figures"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, KeyError, ValueError, TypeError, ImportError) as exc:
        print("Expansion analysis stopped: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
