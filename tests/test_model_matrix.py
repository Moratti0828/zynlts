"""Matrix orchestration recovery and offline comparison provenance tests.

All APIs are local fakes. These tests never call a model or touch platform data.
"""
from collections import Counter
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend import benchmark_v2 as scorer, experiment_v2 as experiment
from scripts import run_model_matrix as matrix
from scripts import summarize_model_matrix as analysis


def fixture_bank():
    articles = []
    for language in ("zh", "en"):
        article_id, paragraph_id = "article-" + language, "article-" + language + ":p001"
        text = "新结果为七。" if language == "zh" else "The new result is seven."
        articles.append({"id": article_id, "title": "Test source", "language": language,
            "source_cluster_id": "source-" + language, "split": "development", "annotation_state": "ai_checked",
            "human_review_count": 0, "published_at": "2026-01-01", "paragraphs": [{"id": paragraph_id, "text": text}],
            "presented_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "questions": [
                {"id": "q01", "prompt": "Select the reported result.", "dimension": "D1", "kind": "choice",
                 "options": {"A": "Seven", "B": "Eight"}, "correct_option": "A", "evidence_sets": [[paragraph_id]]},
                {"id": "q02", "prompt": "Name the result.", "dimension": "D2", "kind": "short",
                 "answers": ["seven"], "evidence_sets": [[paragraph_id]]},
                {"id": "q03", "prompt": "Give the number (units).", "dimension": "D1", "kind": "numeric",
                 "value": "7", "unit": "units", "absolute_tolerance": "0", "evidence_sets": [[paragraph_id]]},
                {"id": "q04", "prompt": "Who supplied an unreported name?", "dimension": "D6", "kind": "unanswerable",
                 "evidence_sets": [], "missing_information": "The supplier is not reported."}]})
    return {"schema_version": "reading-bank-v2", "bank_version": "test-dev", "formal": False,
            "human_review_count": 0, "articles": articles}


class FakeApi:
    def __init__(self):
        self.bank = fixture_bank()
        self.model = {"id": "m", "name": "Test model", "provider": "ollama", "model": "test:fixed",
            "digest": "frozen-digest", "expected_digest": "frozen-digest", "base_url": "http://test.invalid",
            "release_date": "2024-01-01", "available": True, "temporal_verified": True}
        self.calls = Counter()
        self.runs = {}
        self.creation_response_lost = False
        self.interrupted_first_get = False
        self.source_hash_changed = False

    def make_run(self, body):
        items = matrix.selection(self.bank, body.get("article_ids"), body.get("question_ids"), body.get("question_limit"))
        bank = analysis.selected_bank(self.bank, items)
        identity = "run-" + f"{len(self.runs) + 1:012x}"
        config = {**copy.deepcopy(body), "article_ids": body.get("article_ids", [a["id"] for a in self.bank["articles"]]),
            "question_limit": len(items), "seed": 42, "num_ctx": body.get("num_ctx", 8192), "num_thread": 4,
            "grader_version": scorer.VERSION, "runner_version": experiment.RUNNER_VERSION,
            "prompt_version": experiment.PROMPT_VERSION, "output_schema": experiment.SCHEMA}
        # The platform freezes this filter through its selected bank/plan;
        # legacy config does not redundantly include question_ids.
        config.pop("question_ids", None)
        run = {"id": identity, "protocol": "reading-experiment-v2", "status": "completed", "formal": False,
            "config": config, "plan": [{"model_id": "m", "article_id": p["article_id"], "question_id": p["question_id"]} for p in items],
            "snapshots": {"bank": bank, "bank_sha256": matrix.digest(bank), "source_bank_sha256": matrix.digest(self.bank),
                          "models": [copy.deepcopy(self.model)], "output_schema": experiment.SCHEMA},
            "results": [], "attempts": [], "progress": {"done": len(items), "total": len(items)}}
        for index, item in enumerate(items):
            article = next(a for a in bank["articles"] if a["id"] == item["article_id"])
            question = next(q for q in article["questions"] if q["id"] == item["question_id"])
            response = {"answer": "", "unit": "", "evidence_ids": [], "confidence": .8, "abstain": False}
            if question["kind"] == "unanswerable":
                response["abstain"] = True
            else:
                response["answer"] = {"choice": "A", "short": "seven", "numeric": "7"}[question["kind"]]
                response["unit"] = "units" if question["kind"] == "numeric" else ""
                response["evidence_ids"] = [article["paragraphs"][0]["id"]] if body["mode"] == "with_context" else []
            attempt_id = "attempt-" + f"{index + 1:012x}"
            metrics = scorer.grade(question, response, [p["id"] for p in article["paragraphs"]], language=article["language"])
            if body["mode"] == "no_context":
                metrics = experiment._no_evidence_view(metrics)
            row = {"model_id": "m", "model_name": "Test model", "article_id": article["id"],
                "article_sha256": article["presented_text_sha256"], "question_id": question["id"],
                "question": question["prompt"], "kind": question["kind"], "dimension": question["dimension"],
                "language": article["language"], "answer": response["answer"], "unit": response["unit"],
                "evidence": response["evidence_ids"], "confidence": response["confidence"], "abstain": response["abstain"],
                "raw_response": json.dumps(response), "response": response, "error": None, "metrics": metrics,
                "attempt_id": attempt_id, "prompt_sha256": "prompt-frozen", "budget": {"exact": False, "input_tokens": 100},
                "latency_s": 1, "input_tokens": 50, "output_tokens": 20}
            run["results"].append(row)
            run["attempts"].append({"id": attempt_id, "model_id": "m", "article_id": article["id"], "question_id": question["id"],
                "prompt_sha256": "prompt-frozen", "status": "recorded_response"})
        return run

    def request(self, path, body=None, raw=False):
        self.calls[("POST" if body is not None else "GET", path)] += 1
        if path == "/api/health":
            return {"status": "ok", "version": "test"}
        if path == "/api/models":
            return {"models": [copy.deepcopy(self.model)]}
        if path == "/api/v2/banks/test-bank":
            return experiment.bank_info("test-bank", self.bank)
        if path == "/api/v2/runs":
            run = self.make_run(body)
            self.runs[run["id"]] = run
            if self.creation_response_lost:
                raise matrix.ApiError("Connection lost after server committed creation")
            return {"id": run["id"]}
        if path.endswith("/resume"):
            return {"status": "queued"}
        identity = path.split("/")[4]
        run = copy.deepcopy(self.runs[identity])
        if self.source_hash_changed:
            run["snapshots"]["source_bank_sha256"] = "changed"
        if self.interrupted_first_get:
            self.interrupted_first_get = False
            run.update(status="interrupted", results=[], attempts=[], progress={"done": 0, "total": len(run["plan"])})
        if path.endswith("/export?format=csv"):
            return experiment.export_run(run, "csv")[0]
        return run


def arguments(output_dir, modes=None):
    return matrix.parser().parse_args(["--models", "m", "--bank", "test-bank", "--strict-budget", "false",
                                      "--poll-seconds", "0.01", "--modes", *(modes or ["with_context"]), "--output-dir", str(output_dir)])


def run_quietly(args, api):
    with redirect_stdout(io.StringIO()):
        return matrix.run_matrix(args, api)


class MatrixRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.api = FakeApi()

    def tearDown(self):
        self.temp.cleanup()

    def test_lost_creation_response_is_never_retried_implicitly(self):
        args = arguments(self.path)
        self.api.creation_response_lost = True
        with self.assertRaises(matrix.ApiError):
            run_quietly(args, self.api)
        saved = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["jobs"][0]["status"], "creation_unknown")
        self.assertEqual(len(self.api.runs), 1)
        with self.assertRaisesRegex(RuntimeError, "Creation outcome unknown"):
            run_quietly(args, self.api)
        self.assertEqual(self.api.calls[("POST", "/api/v2/runs")], 1)

    @patch.object(matrix.time, "sleep")
    def test_interrupted_run_resumes_the_same_id_and_completed_rerun_skips_calls(self, _sleep):
        args = arguments(self.path)
        self.api.interrupted_first_get = True
        first = run_quietly(args, self.api)
        job = first["jobs"][0]
        self.assertTrue(job["complete"])
        self.assertEqual(self.api.calls[("POST", "/api/v2/runs")], 1)
        self.assertEqual(self.api.calls[("POST", "/api/v2/runs/" + job["run_id"] + "/resume")], 1)
        calls_before = self.api.calls.copy()
        second = run_quietly(args, self.api)
        self.assertEqual(second["jobs"][0]["run_id"], job["run_id"])
        self.assertEqual(self.api.calls, calls_before)
        run = analysis.read_json(self.path / job["json"])
        self.assertEqual(len({(r["article_id"], r["question_id"]) for r in run["results"]}), len(run["plan"]))

    def test_source_input_hash_change_stops_before_any_duplicate_creation(self):
        args = arguments(self.path)
        self.api.source_hash_changed = True
        with self.assertRaisesRegex(ValueError, "Source bank changed"):
            run_quietly(args, self.api)
        self.assertEqual(self.api.calls[("POST", "/api/v2/runs")], 1)
        saved = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["jobs"][0]["run_id"])

    def test_question_subset_uses_frozen_plan_when_config_omits_redundant_filter(self):
        args = arguments(self.path, ["no_context"])
        args.question_ids = ["q01", "q02"]
        manifest = run_quietly(args, self.api)
        self.assertTrue(manifest["jobs"][0]["complete"])
        run = self.api.runs[manifest["jobs"][0]["run_id"]]
        self.assertNotIn("question_ids", run["config"])
        self.assertEqual(len(run["plan"]), 4)
        self.assertEqual({p["question_id"] for p in run["plan"]}, {"q01", "q02"})

    def test_explicit_context_and_reference_switch_are_frozen_before_post(self):
        self.api.bank["annotation_origin"] = "external_public_benchmark"
        args = arguments(self.path)
        with self.assertRaisesRegex(ValueError, "Historical public reference"):
            run_quietly(args, self.api)
        self.assertEqual(self.api.calls[("POST", "/api/v2/runs")], 0)
        args.strict_time, args.num_ctx = "false", 4096
        manifest = run_quietly(args, self.api)
        job = manifest["jobs"][0]
        self.assertEqual(job["request"]["num_ctx"], 4096)
        self.assertFalse(job["request"]["strict_time"])
        self.assertTrue(job["complete"])

    def test_legacy_default_manifest_without_new_options_remains_resumable(self):
        args = arguments(self.path)
        first = run_quietly(args, self.api)
        saved = copy.deepcopy(first)
        for key in ("num_ctx", "strict_time"):
            saved["specification"].pop(key)
        (self.path / "manifest.json").write_text(json.dumps(saved), encoding="utf-8")
        second = run_quietly(args, self.api)
        self.assertEqual(second["jobs"][0]["run_id"], first["jobs"][0]["run_id"])
        self.assertEqual(self.api.calls[("POST", "/api/v2/runs")], 1)


class AnalysisIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.matrix_dir = self.path / "matrix"
        self.api = FakeApi()
        run_quietly(arguments(self.matrix_dir, ["with_context", "no_context"]), self.api)

    def tearDown(self):
        self.temp.cleanup()

    def inventory(self):
        return analysis.inventory([self.matrix_dir], expected_models=["m"], expected_main=8,
                                  expected_no_context=8, expected_articles_per_language=1)

    def test_known_legacy_runner_can_be_read_but_not_mixed_with_new_runner(self):
        legacy_dir = self.path / "legacy"
        legacy = "reading-runner-v2.1-attempt-log-20261013"
        versions = {"grader_version": scorer.VERSION, "runner_version": legacy, "prompt_version": experiment.PROMPT_VERSION}
        with patch.object(experiment, "RUNNER_VERSION", legacy), patch.object(matrix, "client_versions", return_value=versions):
            run_quietly(arguments(legacy_dir, ["with_context", "no_context"]), FakeApi())
        audit = analysis.inventory([legacy_dir], expected_models=["m"], expected_main=8,
                                   expected_no_context=8, expected_articles_per_language=1)
        self.assertTrue(audit["complete"])
        with self.assertRaisesRegex(analysis.IntegrityError, "version mismatch"):
            analysis.inventory([self.matrix_dir, legacy_dir], expected_main=8,
                               expected_no_context=8, expected_articles_per_language=1)

    def test_complete_matrix_validates_and_no_context_evidence_is_na(self):
        audit = self.inventory()
        self.assertTrue(audit["complete"])
        result = analysis.analyze(audit, repetitions=200)
        row = next(r for r in result["numeric_table"] if (r["model_id"], r["mode"], r["language"], r["question_kind"], r["metric"]) == ("m", "no_context", "en", "all", "evidence_exact_answerable"))
        self.assertIsNone(row["estimate"])
        self.assertEqual(row["denominator"], 0)
        choice = next(r for r in result["numeric_table"] if (r["mode"], r["language"], r["question_kind"], r["metric"]) == ("with_context", "en", "choice", "choice_accuracy"))
        self.assertEqual((choice["estimate"], choice["denominator"]), (1, 1))
        self.assertEqual(result["protocol"]["hypothesis_tests"], "none")

    def test_modified_csv_is_rejected_even_if_json_is_unchanged(self):
        manifest = analysis.read_json(self.matrix_dir / "manifest.json")
        path = self.matrix_dir / manifest["jobs"][0]["csv"]
        path.write_bytes(path.read_bytes() + b"corruption")
        with self.assertRaisesRegex(analysis.IntegrityError, "CSV export hash mismatch"):
            self.inventory()

    def test_resealed_wrong_json_metrics_are_rejected(self):
        manifest_path = self.matrix_dir / "manifest.json"
        manifest = analysis.read_json(manifest_path)
        job = manifest["jobs"][0]
        path = self.matrix_dir / job["json"]
        run = analysis.read_json(path)
        run["results"][0]["metrics"]["answer_correct"] = 0
        analysis.write_json(path, run)
        # Re-seal both files: row-level scorer consistency must still detect it.
        csv_path = self.matrix_dir / job["csv"]
        csv_path.write_bytes(experiment.export_run(run, "csv")[0])
        job["json_file_sha256"], job["csv_file_sha256"] = analysis.sha_file(path), analysis.sha_file(csv_path)
        analysis.write_json(manifest_path, manifest)
        with self.assertRaisesRegex(analysis.IntegrityError, "metrics disagree"):
            self.inventory()

    def test_pilot_size_cannot_silently_enter_main_matrix(self):
        with self.assertRaisesRegex(analysis.IntegrityError, "expected 160"):
            analysis.inventory([self.matrix_dir])

    def test_incomplete_exports_audit_has_blocker_and_cannot_analyze(self):
        manifest_path = self.matrix_dir / "manifest.json"
        manifest = analysis.read_json(manifest_path)
        manifest["jobs"][1].pop("csv_file_sha256")
        analysis.write_json(manifest_path, manifest)
        audit = self.inventory()
        self.assertFalse(audit["complete"])
        self.assertTrue(audit["blockers"])
        with self.assertRaises(analysis.IncompleteError):
            analysis.analyze(audit)

    def test_allow_incomplete_is_read_only_and_creates_no_report_directory(self):
        target = self.path / "must-not-be-created"
        argv = ["summarize_model_matrix.py", "--matrix-dirs", str(self.path / "missing-input"),
                "--output-dir", str(target), "--allow-incomplete"]
        with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()) as output:
            exit_code = analysis.main()
        self.assertEqual(exit_code, 0)
        self.assertFalse(target.exists())
        self.assertFalse(json.loads(output.getvalue())["complete"])

    def test_error_remains_zero_in_full_denominator_not_valid_subset_only(self):
        rows = [{"source_cluster_id": "a", "kind": "choice", "mode": "with_context",
                 "error_type": None, "metrics": {"choice_accuracy": 1, "output_state": "answer"}},
                {"source_cluster_id": "b", "kind": "choice", "mode": "with_context",
                 "error_type": "transport", "metrics": {"choice_accuracy": 0, "output_state": "error"}}]
        estimate = analysis.estimate(rows, "choice_accuracy", [["a", "b"], ["a", "a"], ["b", "b"]])
        self.assertEqual(estimate["estimate"], .5)
        self.assertEqual(estimate["denominator"], 2)
        self.assertEqual(estimate["valid_subset_estimate"], 1)
        self.assertEqual(estimate["valid_subset_n"], 1)

    def test_paired_contrast_is_exact_question_match_not_all_question_mean(self):
        left = [{"article_id": "a", "question_id": "q1", "source_cluster_id": "s", "kind": "choice", "mode": "with_context", "metrics": {"choice_accuracy": 1}}]
        right = [{**left[0], "mode": "no_context", "metrics": {"choice_accuracy": 0}}]
        delta = analysis.paired_difference(left, right, "choice_accuracy", [["s"]])
        self.assertEqual((delta["difference"], delta["paired_items"]), (1, 1))
        right[0]["question_id"] = "q2"
        with self.assertRaisesRegex(analysis.IntegrityError, "unequal question keys"):
            analysis.paired_difference(left, right, "choice_accuracy", [["s"]])


if __name__ == "__main__":
    unittest.main()
