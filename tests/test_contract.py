import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import scoring, server


class GraderContract(unittest.TestCase):
    def setUp(self):
        self.q = {"type": "fact", "answers": ["上海"], "evidence": ["地点为上海。"]}
        self.r = {"answer": "上海", "evidence": ["地点为上海。"], "abstain": False, "confidence": .8}

    def test_good_and_known_bad_are_distinguished(self):
        good = scoring.grade(self.q, self.r, "地点为上海。")
        bad = scoring.grade(self.q, {**self.r, "answer": "北京", "evidence": ["地点为北京。"]}, "地点为上海。")
        self.assertEqual((good["em"], good["evidence_f1"]), (1, 1))
        self.assertEqual((bad["em"], bad["evidence_f1"]), (0, 0))

    def test_numeric_sign_and_percentage_are_not_lost(self):
        self.assertNotEqual(scoring.normalize("-3"), scoring.normalize("3"))
        self.assertNotEqual(scoring.normalize("5%"), scoring.normalize("5"))
        self.assertNotEqual(scoring.normalize("−3"), scoring.normalize("3"))
        self.assertNotEqual(scoring.normalize("-.5"), scoring.normalize(".5"))
        self.assertEqual(scoring.normalize("3,000"), scoring.normalize("3000"))

    def test_missing_confidence_and_no_evidence_are_not_fabricated(self):
        impossible = {"type": "unanswerable", "answers": ["无法确定"], "evidence": []}
        metrics = scoring.grade(impossible, {**self.r, "abstain": True, "confidence": None}, "地点为上海。")
        self.assertEqual(metrics["em"], 1)
        self.assertIsNone(metrics["brier"])
        self.assertIsNone(metrics["evidence_f1"])

    def test_request_errors_remain_in_accuracy_denominator(self):
        rows = [{"model_id": "m", "type": "fact", "error": None, "metrics": {"em": 1, "f1": 1, "abstention_correct": 1, "brier": None}, "latency_s": 1, "abstain": False}, {"model_id": "m", "type": "fact", "error": "timeout", "metrics": {"em": 0, "f1": 0, "abstention_correct": None, "brier": None}, "latency_s": 180, "abstain": False}]
        result = scoring.summarize(rows, [{"id": "m", "name": "M"}])[0]
        self.assertEqual(result["em"], .5)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["mean_latency_s"], 1)


class EvaluationContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = server.DB
        server.DB = Path(self.temp.name) / "test.sqlite3"
        with server.connect() as db:
            db.execute("CREATE TABLE objects(kind TEXT,id TEXT,value TEXT,PRIMARY KEY(kind,id))")
        self.article = {"id": "a1", "title": "示例", "published_at": "2025-01-01", "source_url": "https://example.org", "text": "地点为上海。", "questions": [{"id": "q1", "prompt": "地点？", "type": "fact", "answers": ["上海"], "evidence": ["地点为上海。"], "reviewed": True}]}
        self.model = {"id": "m", "name": "M", "model": "test", "provider": "ollama", "base_url": "http://127.0.0.1:11434", "release_date": "2024-01-01", "release_source": "https://example.org/model", "expected_digest": "fixed"}
        server.put("model", "m", self.model)

    def tearDown(self):
        server.DB = self.old
        self.temp.cleanup()

    def test_corpus_rejects_corrupted_hash_and_nonexistent_evidence(self):
        with self.assertRaisesRegex(ValueError, "sha256"):
            server.validate_article({**copy.deepcopy(self.article), "sha256": "bad"})
        bad = copy.deepcopy(self.article)
        bad["questions"][0]["evidence"] = ["不存在"]
        with self.assertRaisesRegex(ValueError, "原文"):
            server.validate_article(bad)

    def test_model_date_and_unpinned_versions_are_rejected(self):
        for release, verified in [("2025-01-01", True), ("2024-01-01", False)]:
            with self.subTest(release=release, verified=verified), patch.object(server, "corpus", return_value={"articles": [self.article]}), patch.object(server, "model_status", return_value={**self.model, "release_date": release, "available": True, "temporal_verified": verified}):
                with self.assertRaises(ValueError):
                    server.create_run({"model_ids": ["m"], "article_ids": ["a1"]})

    def test_gold_answer_and_evidence_never_sent_to_model(self):
        question = {"prompt": "Which city?", "answers": ["SECRET_GOLD"], "evidence": ["SECRET_EVIDENCE"]}
        config = {"mode": "with_context", "temperature": 0, "max_tokens": 256}
        response = {"message": {"content": '{"answer":"unknown","evidence":[],"abstain":true}'}}
        with patch.object(server, "request_json", return_value=response) as sender:
            server.call_model(self.model, "PUBLIC_PASSAGE", question, config)
            sent = str(sender.call_args)
            self.assertIn("PUBLIC_PASSAGE", sent)
            self.assertNotIn("SECRET_GOLD", sent)
            self.assertNotIn("SECRET_EVIDENCE", sent)

    def test_malformed_response_does_not_become_success(self):
        for text in ['hello', '{"answer":"x","evidence":[],"abstain":"false"}', '{"answer":"x","evidence":[],"abstain":false,"confidence":NaN}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                server.parse_response(text)

    def test_compact_dates_and_false_refusal_are_rejected(self):
        for date in ["20240101", "2024-W01-1"]:
            with self.subTest(date=date), self.assertRaises(ValueError):
                server.validate_article({**copy.deepcopy(self.article), "first_published_at": date})
        with self.assertRaisesRegex(ValueError, "拒答输出不一致"):
            server.parse_response('{"answer":"42","evidence":[],"abstain":true}')

    def test_full_input_not_only_passage_is_bounded(self):
        messages = [{"role": "system", "content": "x" * 3000}, {"role": "user", "content": "x" * 6000}]
        with self.assertRaisesRegex(ValueError, "完整提示词"):
            server.validate_input_budget(messages, 256)

    def test_post_response_digest_change_invalidates_final_question(self):
        article = server.validate_article(copy.deepcopy(self.article))
        fixed = {**self.model, "available": True, "digest": "fixed", "temporal_verified": True}
        run = {"id": "run-abcdefabcdef", "status": "queued", "config": {"mode": "with_context", "max_tokens": 256}, "progress": {"done": 0, "total": 1}, "summary": [], "results": [], "snapshots": {"models": [fixed], "articles": [article]}, "cancel_requested": False}
        server.put("run", run["id"], run)
        raw = '{"answer":"上海","evidence":["地点为上海。"],"confidence":1,"abstain":false}'
        with patch.object(server, "model_status", side_effect=[fixed, fixed, {**fixed, "digest": "changed"}]), patch.object(server, "call_model", return_value=(raw, {}, "hash")):
            server.execute_run(run["id"], [(article, article["questions"][0])])
        result = server.get("run", run["id"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["results"][0]["metrics"]["em"], 0)
        self.assertEqual(result["results"][0]["raw_response"], raw)


if __name__ == "__main__":
    unittest.main()
