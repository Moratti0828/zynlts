"""Meaningful provenance, completion and heterogeneous-cohort guard tests.

All runs use an in-process fake API. No model or server is contacted.
"""
from contextlib import redirect_stdout
import copy
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_model_matrix import FakeApi, run_quietly
from backend import experiment_v2 as runner
from scripts import run_model_matrix as matrix
from scripts import summarize_expansion_20261024 as expansion


class UniqueFakeApi(FakeApi):
    identities = itertools.count(1)

    def make_run(self, body):
        run = super().make_run(body)
        run["id"] = "run-" + f"{next(self.identities):012x}"
        for i, (row, attempt) in enumerate(zip(run["results"], run["attempts"])):
            identity = "attempt-" + run["id"][4:] + f"-{i:03d}"
            row["attempt_id"] = attempt["id"] = identity
        return run


class ExpansionAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "matrices"
        self.root.mkdir()
        self.output = Path(self.temp.name) / "analysis"

    def tearDown(self):
        self.temp.cleanup()

    def make_matrix(self, name="one", mode="with_context", ctx=8192, bank_version="bank-a", public=False, extra=()):
        api = UniqueFakeApi()
        api.bank["bank_version"] = bank_version
        if public:
            api.bank["annotation_origin"] = "external_public_benchmark"
            api.bank["split"] = "reference"
        args = matrix.parser().parse_args(["--models", "m", "--bank", "test-bank", "--strict-budget", "false",
            "--strict-time", "false" if public else "true", "--num-ctx", str(ctx), "--poll-seconds", "0.01",
            "--modes", mode, "--output-dir", str(self.root / name), *extra])
        manifest = run_quietly(args, api)
        return self.root / name, manifest

    def rewrite_run(self, directory, manifest, change):
        job = manifest["jobs"][0]
        path = directory / job["json"]
        run = expansion.read_json(path)
        change(run)
        matrix.atomic_json(path, run)
        csv_path = directory / job["csv"]
        csv_path.write_bytes(runner.export_run(run, "csv")[0])
        job.update(json_file_sha256=expansion.sha_file(path), csv_file_sha256=expansion.sha_file(csv_path))
        matrix.atomic_json(directory / "manifest.json", manifest)
        return run

    def test_json_tamper_is_rejected_even_when_incomplete_allowed(self):
        directory, manifest = self.make_matrix()
        path = directory / manifest["jobs"][0]["json"]
        run = expansion.read_json(path)
        run["results"][0]["latency_s"] = 999
        matrix.atomic_json(path, run)
        with self.assertRaisesRegex(expansion.IntegrityError, "JSON export hash"):
            expansion.inventory(self.root)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(expansion.main(["--matrix-root", str(self.root), "--output-dir", str(self.output), "--allow-incomplete"]), 2)
        self.assertFalse(self.output.exists())

    def test_missing_planned_matrix_returns_progress_without_artifacts(self):
        plan = {"schema_version": "reading-expansion-stage-v1", "formal": False,
                "configurations": [{"name": "not-started"}]}
        matrix.atomic_json(self.root / "test-plan.json", plan)
        with redirect_stdout(io.StringIO()) as capture:
            code = expansion.main(["--matrix-root", str(self.root), "--output-dir", str(self.output), "--allow-incomplete"])
        self.assertEqual(code, 0)
        self.assertIn("Missing planned matrix", capture.getvalue())
        self.assertFalse(self.output.exists())

    def test_unplanned_matrix_is_not_silently_added_to_existing_stage(self):
        self.make_matrix("unexpected")
        matrix.atomic_json(self.root / "declared-plan.json", {"schema_version": "reading-expansion-stage-v1", "formal": False,
            "configurations": [{"name": "declared-but-missing"}]})
        with self.assertRaisesRegex(expansion.IntegrityError, "Unplanned matrix"):
            expansion.inventory(self.root)

    def test_failed_full_run_is_not_accepted_as_complete(self):
        directory, manifest = self.make_matrix()
        self.rewrite_run(directory, manifest, lambda run: run.update(status="failed"))
        manifest["jobs"][0]["final_status"] = "failed"
        matrix.atomic_json(directory / "manifest.json", manifest)
        audit = expansion.inventory(self.root)
        self.assertFalse(audit["complete"])
        self.assertIn("Unfinished/failed", " ".join(audit["blockers"]))
        with self.assertRaises(expansion.IncompleteError):
            expansion.analyze(audit, 200)

    def test_banks_contexts_and_paired_subsets_are_never_pooled(self):
        self.make_matrix("a8", ctx=8192)
        small = ("--article-ids", "article-zh", "--question-ids", "q01", "q02")
        self.make_matrix("a4", ctx=4096, extra=small)
        self.make_matrix("a4-control", ctx=4096, mode="no_context", extra=small)
        self.make_matrix("b8", ctx=8192, bank_version="different-bank")
        audit = expansion.inventory(self.root)
        self.assertTrue(audit["complete"])
        bundle = expansion.analyze(audit, 200)
        self.assertEqual(len(bundle["banks"]), 2)
        self.assertEqual(len(bundle["coverage"]), 6)
        window = [r for r in bundle["paired_differences"] if r["comparison"] == "larger_minus_smaller_context_exact_subset"]
        self.assertTrue(window)
        self.assertTrue(all((r["left_total_questions"], r["right_total_questions"], r["matched_questions"], r["excluded_left_questions"]) == (4, 2, 2, 2) for r in window))
        self.assertTrue(all(r["left_num_ctx"] == 8192 and r["right_num_ctx"] == 4096 for r in window))
        # Same article/question IDs in a different canonical bank are never paired.
        self.assertEqual(len({r["source_bank_sha256"] for r in bundle["paired_differences"]}), 1)

    def test_public_evidence_is_auxiliary_and_missing_tasks_are_na(self):
        self.make_matrix(public=True, extra=("--question-ids", "q02"))
        bundle = expansion.analyze(expansion.inventory(self.root), 200)
        rows = [r for r in bundle["numeric_table"] if r["question_kind"] == "all"]
        evidence = [r for r in rows if r["metric_key"].startswith("evidence_")]
        self.assertTrue(evidence)
        self.assertTrue(all(r["metric_role"] == "auxiliary_span_proxy" and r["metric"].startswith("span_proxy_") for r in evidence))
        choice = [r for r in rows if r["metric"] == "choice_accuracy"]
        self.assertTrue(all(r["estimate"] is None and r["denominator"] == 0 for r in choice))
        self.assertTrue(all(r["ci_lower"] is None for r in rows))  # one source cluster per language

    def test_gpu_claim_requires_matching_device_artifact(self):
        directory, manifest = self.make_matrix()
        manifest["jobs"][0]["gpu_fully_resident_observed"] = True
        matrix.atomic_json(directory / "manifest.json", manifest)
        with self.assertRaisesRegex(expansion.IntegrityError, "GPU residency"):
            expansion.inventory(self.root)

    def test_attempt_ids_must_be_globally_unique(self):
        first_dir, first = self.make_matrix("first")
        first_run = expansion.read_json(first_dir / first["jobs"][0]["json"])
        duplicate = first_run["attempts"][0]["id"]
        second_dir, second = self.make_matrix("second", mode="no_context")
        def alter(run):
            run["attempts"][0]["id"] = duplicate
            run["results"][0]["attempt_id"] = duplicate
        self.rewrite_run(second_dir, second, alter)
        with self.assertRaisesRegex(expansion.IntegrityError, "Attempt ID repeated"):
            expansion.inventory(self.root)

    def test_text_bundle_records_provenance_and_artifact_hashes(self):
        self.make_matrix(extra=("--article-ids", "article-en"))
        bundle = expansion.analyze(expansion.inventory(self.root), 200)
        expansion.write_bundle(bundle, self.output, skip_figures=True)
        manifest = expansion.read_json(self.output / "bundle-manifest.json")
        self.assertTrue(manifest["complete_inputs"])
        self.assertFalse(manifest["formal"])
        for item in manifest["outputs"]:
            self.assertEqual(expansion.sha_file(self.output / item["path"]), item["sha256"])
        self.assertTrue((self.output / "analysis-report.md").is_file())
        self.assertTrue((self.output / "stats-appendix.md").is_file())
        self.assertTrue((self.output / "figure-catalog.md").is_file())


if __name__ == "__main__":
    unittest.main()
