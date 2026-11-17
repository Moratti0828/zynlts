import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from backend import server, experiment_v2 as runner


class ExperimentV2Contract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "test.sqlite3"
        with server.connect() as db:
            db.execute("CREATE TABLE objects(kind TEXT,id TEXT,value TEXT,PRIMARY KEY(kind,id))")
        text = "A report names the new result."
        self.article = {"id": "article", "title": "Development", "language": "en",
            "source_cluster_id": "source", "split": "development", "annotation_state": "ai_checked",
            "published_at": "2026-01-01", "paragraphs": [{"id": "article:p001", "text": text}],
            "presented_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "questions": [{"id": "q1", "prompt": "What is the result?", "dimension": "D1", "kind": "short",
                "answers": ["SECRET_GOLD"], "evidence_sets": [["article:p001"]]},
                {"id": "q2", "prompt": "Who supplied the unpublished detail?", "dimension": "D6", "kind": "unanswerable",
                 "evidence_sets": [], "missing_information": "SECRET_MISSING_REASON"}]}
        self.bank = {"schema_version": "reading-bank-v2", "bank_version": "draft", "articles": [self.article]}
        self.model = {"id": "m", "name": "Model", "provider": "ollama", "model": "test",
            "base_url": "http://localhost:11434", "digest": "fixed", "expected_digest": "fixed",
            "release_date": "2024-01-01", "release_source": "https://example.org", "available": True, "temporal_verified": True}
        server.put("model", "m", self.model)
        self.preflight = {"allowed": True, "method": "test_budget", "input_tokens": 80,
            "reserved_margin_tokens": 512, "exact": False, "rendered_prompt": None}

    def tearDown(self):
        server.DB = self.old_db
        self.temp.cleanup()

    def create(self, **overrides):
        with patch.object(runner, "banks", return_value={"draft": copy.deepcopy(self.bank)}), \
             patch.object(server, "model_status", return_value=self.model), \
             patch.object(runner, "prepare_budget", return_value=self.preflight), \
             patch.object(server, "QUEUE", Mock()):
            return runner.create_run({"bank_id": "draft", "model_ids": ["m"], "allow_draft": True,
                "strict_time": True, "strict_budget": False, "bootstrap_repetitions": 0, **overrides}, server)["id"]

    def test_public_prompt_does_not_leak_gold_or_review_metadata(self):
        q = {**self.article["questions"][0], "operation": "SECRET_OPERATION", "human_reviews": [{"reviewer_id": "SECRET_REVIEW"}]}
        prompt = json.dumps(runner.messages(self.article, q, "with_context"))
        for secret in ["SECRET_GOLD", "SECRET_OPERATION", "SECRET_REVIEW"]:
            self.assertNotIn(secret, prompt)
        unknown = json.dumps(runner.messages(self.article, self.article["questions"][1], "with_context"))
        self.assertNotIn("SECRET_MISSING_REASON", unknown)
        self.assertIn("article:p001", prompt)

    def test_draft_cannot_run_as_formal_or_disable_formal_gates(self):
        with self.assertRaises(ValueError):
            self.create(allow_draft=False)
        with self.assertRaises(ValueError):
            self.create(allow_draft=False, strict_time=False, strict_budget=True)

    def test_declared_json_contract_rejects_missing_extra_and_invalid_confidence(self):
        valid = {"answer": "A", "unit": "", "evidence_ids": [], "confidence": .8, "abstain": False}
        self.assertEqual(runner.parse_response(json.dumps(valid)), valid)
        for missing in valid:
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                runner.parse_response(json.dumps({k: v for k, v in valid.items() if k != missing}))
        with self.assertRaisesRegex(ValueError, "五个JSON字段"):
            runner.parse_response(json.dumps({**valid, "unexpected": "must not be silently dropped"}))
        for confidence in [None, True, -0.1, 1.1, float("inf")]:
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                runner.parse_response(json.dumps({**valid, "confidence": confidence}))
        with self.assertRaisesRegex(ValueError, "unit"):
            runner.parse_response(json.dumps({**valid, "answer": "", "abstain": True, "unit": "%"}))

    def test_native_context_limit_is_explicit_and_oversized_run_is_not_saved(self):
        self.model["native_context_tokens"] = 4096
        with self.assertRaisesRegex(ValueError, "原生上限"):
            self.create()
        self.assertEqual(server.all_objects("run"), [])
        identity = self.create(num_ctx=4096)
        self.assertEqual(server.get("run", identity)["config"]["num_ctx"], 4096)
        for value in (True, 1000, 8193):
            with self.assertRaisesRegex(ValueError, "上下文窗口"):
                self.create(num_ctx=value)

    def test_public_historical_bank_requires_explicit_non_temporal_draft(self):
        self.bank["annotation_origin"] = "external_public_benchmark"
        with self.assertRaisesRegex(ValueError, "公开历史参考集"):
            self.create()
        self.assertEqual(server.all_objects("run"), [])
        identity = self.create(strict_time=False)
        run = server.get("run", identity)
        self.assertFalse(run["formal"])
        self.assertFalse(run["config"]["strict_time"])

    def test_future_publication_is_rejected_before_formal_run_is_persisted(self):
        self.article["published_at"] = "2099-01-01"
        self.article["annotation_state"] = "frozen"
        for question in self.article["questions"]:
            question["human_reviews"] = [{"reviewer_id": "synthetic_fixture_" + str(i),
                "decision": "accepted", "reviewed_at": "2026-10-13"} for i in (1, 2)]
            question["adjudication_complete"] = True
        # Constructed review records belong only to this temporary regression fixture.
        with self.assertRaisesRegex(ValueError, "未来日期"):
            self.create(allow_draft=False, strict_budget=True)
        self.assertEqual(server.all_objects("run"), [])
        # Turning off the training-date comparison cannot legitimise a future article.
        with self.assertRaisesRegex(ValueError, "未来日期"):
            self.create(strict_time=False)

    def test_bank_discovery_ignores_non_dictionary_json_fixtures(self):
        annotation = Path(self.temp.name) / "data" / "annotation"
        annotation.mkdir(parents=True)
        for index, fixture in enumerate([[], ["response fixture"], None, 3, "fixture"]):
            (annotation / f"non_bank_{index}.json").write_text(json.dumps(fixture), encoding="utf-8")
        (annotation / "fixture_bank.json").write_text(json.dumps(self.bank), encoding="utf-8")
        bridge = SimpleNamespace(ROOT=Path(self.temp.name), all_objects=Mock(return_value=[]))
        found = runner.banks(bridge)
        self.assertEqual(found, {"fixture_bank": self.bank})

    def test_800_planned_questions_are_not_truncated_to_200(self):
        self.article["questions"] = [{**self.article["questions"][0], "id": "q" + str(i)} for i in range(800)]
        identity = self.create(question_limit=800)
        run = server.get("run", identity)
        self.assertEqual((len(run["plan"]), run["progress"]["total"]), (800, 800))
        self.assertEqual(run["evaluation"]["summaries"]["m"]["en"]["by_question_kind"]["short"]["planned_questions"], 800)
        self.assertEqual(run["evaluation"]["summaries"]["m"]["en"]["primary_metrics"]["short_em"], 0)

    def test_cancel_and_resume_only_unfinished_keep_failure_denominator(self):
        identity = self.create()
        first = '{"answer":"SECRET_GOLD","unit":"","evidence_ids":["article:p001"],"confidence":1,"abstain":false}'
        def interrupted_call(*args):
            run = server.get("run", identity)
            run["cancel_requested"] = True
            server.put("run", identity, run)
            return first, {}
        with patch.object(server, "model_status", return_value=self.model), \
             patch.object(runner, "prepare_budget", return_value=self.preflight), \
             patch.object(runner, "call_model", side_effect=interrupted_call):
            runner.execute_run(identity, server)
        stopped = server.get("run", identity)
        self.assertEqual(stopped["status"], "cancelled")
        self.assertEqual(len(stopped["results"]), 1)
        with patch.object(server, "QUEUE", Mock()):
            self.assertEqual(runner.resume_run(identity, server)["remaining"], 1)
        refusal = '{"answer":"","unit":"","evidence_ids":[],"confidence":1,"abstain":true}'
        with patch.object(server, "model_status", return_value=self.model), \
             patch.object(runner, "prepare_budget", return_value=self.preflight), \
             patch.object(runner, "call_model", return_value=(refusal, {})) as call:
            runner.execute_run(identity, server)
        final = server.get("run", identity)
        self.assertEqual(call.call_count, 1)
        self.assertEqual((final["status"], len(final["results"])), ("completed", 2))
        self.assertEqual(len({r["question_id"] for r in final["results"]}), 2)

    def test_post_response_digest_change_is_zero_and_raw_is_preserved(self):
        identity = self.create()
        raw = '{"answer":"SECRET_GOLD","unit":"","evidence_ids":["article:p001"],"confidence":0.8,"abstain":false}'
        with patch.object(server, "model_status", side_effect=[self.model, {**self.model, "digest": "other"}]), \
             patch.object(runner, "prepare_budget", return_value=self.preflight), \
             patch.object(runner, "call_model", return_value=(raw, {})):
            runner.execute_run(identity, server)
        run = server.get("run", identity)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["results"][0]["raw_response"], raw)
        self.assertEqual(run["results"][0]["metrics"]["answer_correct"], 0)
        self.assertEqual(run["evaluation"]["summaries"]["m"]["en"]["primary_metrics"]["short_em"], 0)

    def test_no_context_allows_prior_knowledge_and_omits_evidence_scores(self):
        identity = self.create(mode="no_context", question_limit=1)
        raw = '{"answer":"SECRET_GOLD","unit":"","evidence_ids":[],"confidence":0.8,"abstain":false}'
        prompt = runner.messages(self.article, self.article["questions"][0], "no_context")
        self.assertIn("may use existing knowledge", prompt[0]["content"])
        self.assertNotIn(self.article["paragraphs"][0]["text"], prompt[1]["content"])
        with patch.object(server, "model_status", return_value=self.model), \
             patch.object(runner, "prepare_budget", return_value=self.preflight), \
             patch.object(runner, "call_model", return_value=(raw, {})):
            runner.execute_run(identity, server)
        report = server.get("run", identity)["evaluation"]["summaries"]["m"]["en"]
        self.assertEqual(report["primary_metrics"]["short_em"], 1)
        self.assertIsNone(report["primary_metrics"]["evidence_exact_answerable"])
        self.assertIsNone(report["grounded_understanding"])

    def test_raw_native_prompt_and_budget_validation_are_preserved(self):
        identity = self.create(question_limit=1, strict_budget=True)
        exact = {**self.preflight, "exact": True, "rendered_prompt": "NATIVE_PROMPT", "prompt_sha256": "hash"}
        raw = '{"answer":"SECRET_GOLD","unit":"","evidence_ids":["article:p001"],"confidence":0.8,"abstain":false}'
        with patch.object(server, "model_status", return_value=self.model), \
             patch.object(runner, "prepare_budget", return_value=exact), \
             patch.object(runner, "call_model", return_value=(raw, {"input_tokens": 81})):
            runner.execute_run(identity, server)
        run = server.get("run", identity)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["results"][0]["budget"]["runtime_count_delta"], 1)
        self.assertEqual(run["results"][0]["metrics"]["answer_correct"], 0)
        with patch.object(server, "request_json", return_value={"response": raw}) as request:
            runner.call_model(self.model, [{"role": "user", "content": "public"}], exact,
                run["config"], server)
        payload = request.call_args.args[1]
        self.assertTrue(payload["raw"])
        self.assertEqual(payload["prompt"], "NATIVE_PROMPT")
        self.assertNotIn("messages", payload)

    def test_resume_rejects_changed_version_and_bank_snapshot(self):
        identity = self.create()
        run = server.get("run", identity)
        run["status"] = "interrupted"
        saved_version = run["config"]["runner_version"]
        run["config"]["runner_version"] = "old-runner-fixture"
        server.put("run", identity, run)
        with self.assertRaisesRegex(ValueError, "版本"):
            runner.resume_run(identity, server)
        run["config"]["runner_version"] = saved_version
        run["snapshots"]["bank"]["articles"][0]["questions"][0]["answers"] = ["tampered"]
        server.put("run", identity, run)
        with self.assertRaisesRegex(ValueError, "快照"):
            runner.resume_run(identity, server)

    def test_unknown_inflight_attempt_survives_resume_and_new_result_is_linked(self):
        identity = self.create(question_limit=1)
        run = server.get("run", identity)
        run.update(status="interrupted", attempts=[{"id": "attempt-before-interrupt",
            "model_id": "m", "article_id": "article", "question_id": "q1",
            "status": "in_flight", "started_at": "2026-10-13T00:00:00+00:00"}])
        server.put("run", identity, run)
        with patch.object(server, "QUEUE", Mock()):
            self.assertEqual(runner.resume_run(identity, server)["remaining"], 1)
        resumed = server.get("run", identity)
        self.assertEqual(resumed["attempts"][0]["status"], "unknown_outcome_after_interrupt")
        self.assertEqual(resumed["resume_events"][-1]["unknown_inflight_attempts"], 1)
        self.assertIn("reconciled_at", resumed["attempts"][0])
        raw = '{"answer":"SECRET_GOLD","unit":"","evidence_ids":["article:p001"],"confidence":1,"abstain":false}'
        def inspect_then_reply(*args):
            pending = server.get("run", identity)
            self.assertEqual(len(pending["results"]), 0)
            self.assertEqual(pending["attempts"][-1]["status"], "in_flight")
            self.assertNotEqual(pending["attempts"][-1]["id"], "attempt-before-interrupt")
            return raw, {}
        with patch.object(server, "model_status", return_value=self.model), \
             patch.object(runner, "prepare_budget", return_value=self.preflight), \
             patch.object(runner, "call_model", side_effect=inspect_then_reply) as call:
            runner.execute_run(identity, server)
        final = server.get("run", identity)
        self.assertEqual(call.call_count, 1)
        self.assertEqual((final["status"], len(final["results"]), len(final["attempts"])), ("completed", 1, 2))
        self.assertEqual(final["attempts"][0]["status"], "unknown_outcome_after_interrupt")
        self.assertEqual(final["attempts"][1]["status"], "recorded_response")
        self.assertEqual(final["results"][0]["attempt_id"], final["attempts"][1]["id"])
        self.assertIn("finished_at", final["attempts"][1])
        self.assertEqual(final["evaluation"]["summaries"]["m"]["en"]["primary_metrics"]["short_em"], 1)


if __name__ == "__main__":
    unittest.main()
