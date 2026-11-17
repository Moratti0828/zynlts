"""Local fixtures only: no model generation or external network calls."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

from backend import experiment_v2, live_demo, server


class LiveDemoContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB
        server.DB = Path(self.temp.name) / "demo.sqlite3"
        with server.connect() as db:
            db.execute("CREATE TABLE objects(kind TEXT,id TEXT,value TEXT,PRIMARY KEY(kind,id))")
        self.model = {"id": "test-model", "name": "Temporary test model", "provider": "ollama",
                      "model": "test:fixed", "base_url": "http://127.0.0.1:11434",
                      "expected_digest": "fixed", "release_date": "2024-01-01",
                      "release_source": "https://example.org/fixed-model", "native_context_tokens": 8192}
        server.put("model", self.model["id"], self.model)
        self.tags = {"models": [{"name": "test:fixed", "digest": "fixed"}]}
        self.payload = {"model_id": self.model["id"], "preset_id": "zh-reading",
                        "allow_draft": True, "client_request_id": "synthetic-test-request-0001"}

    def tearDown(self):
        server.DB = self.old_db
        self.temp.cleanup()

    def create(self, **overrides):
        with patch.object(server, "request_json", return_value=self.tags), patch.object(server, "QUEUE", Mock()) as queue:
            result = live_demo.create_run({**self.payload, **overrides}, server)
        return result, queue

    def test_status_probes_only_tags_and_excludes_all_gold(self):
        with patch.object(server, "request_json", return_value=self.tags) as request:
            value = live_demo.status(server)
        self.assertTrue(value["ready"])
        self.assertEqual(value["model_calls"], 0)
        self.assertEqual(len(value["presets"]), 4)
        self.assertTrue(all(call.args[0].endswith("/api/tags") for call in request.call_args_list))
        for preset in value["presets"]:
            for question in preset["questions"]:
                self.assertEqual(set(question) - set(live_demo.QUESTION_PUBLIC_FIELDS), set())
                self.assertNotIn("answers", question)
                self.assertNotIn("evidence_sets", question)
            self.assertNotIn("questions", preset["article"])
            self.assertTrue(preset["article"]["paragraphs"])
        self.assertEqual(server.all_objects("run"), [])

    def test_multiple_models_share_a_single_service_tags_probe(self):
        server.put("model", "other", {**self.model, "id": "other", "model": "not-installed"})
        with patch.object(server, "request_json", return_value=self.tags) as request:
            value = live_demo.status(server)
        self.assertEqual(request.call_count, 1)
        other = next(model for model in value["models"] if model["id"] == "other")
        self.assertFalse(other["available"])
        self.assertEqual(other["compatible_preset_ids"], [])

    def test_offline_service_is_a_readable_unavailable_state(self):
        with patch.object(server, "request_json", side_effect=ValueError("模型服务连接失败或超时")):
            value = live_demo.status(server)
        self.assertFalse(value["ready"])
        self.assertEqual(value["status"], "unavailable")
        self.assertIn("连接失败", value["models"][0]["status"])
        self.assertEqual(server.all_objects("run"), [])

    def test_native_four_k_only_exposes_whole_passage_presets_that_fit(self):
        server.put("model", self.model["id"], {**self.model, "native_context_tokens": 4096})
        with patch.object(server, "request_json", return_value=self.tags):
            value = live_demo.status(server)
        model = value["models"][0]
        self.assertEqual(model["demo_context_tokens"], 4096)
        self.assertEqual(model["compatible_preset_ids"], ["zh-quick"])
        result, _ = self.create(preset_id="zh-quick")
        self.assertEqual(result["run"]["config"]["num_ctx"], 4096)
        # The first creation is deliberately not executed by the mock queue.
        # Finish that fixture so the next assertion reaches the budget guard.
        run = server.get("run", result["id"])
        run["status"] = "completed"
        server.put("run", run["id"], run)
        with self.assertRaisesRegex(ValueError, "预算"):
            self.create(preset_id="en-reading", client_request_id="synthetic-test-request-0002")

    def test_changed_bank_is_not_silently_used_under_old_preset(self):
        banks = experiment_v2.banks(server)
        banks[live_demo.BANK_ID]["articles"][0]["title"] += " changed fixture"
        with patch.object(experiment_v2, "banks", return_value=banks), patch.object(server, "request_json", return_value=self.tags):
            value = live_demo.status(server)
            self.assertFalse(value["ready"])
            self.assertEqual(value["presets"], [])
            with self.assertRaisesRegex(ValueError, "版本发生变化"):
                live_demo.create_run(self.payload, server)
        self.assertEqual(server.all_objects("run"), [])

    def test_create_uses_existing_engine_frozen_full_article_and_exact_question_selection(self):
        result, queue = self.create()
        run = result["run"]
        self.assertFalse(result["reused"])
        self.assertEqual(run["protocol"], experiment_v2.PROTOCOL)
        self.assertEqual(run["progress"], {"done": 0, "total": 3})
        self.assertEqual([task["question_id"] for task in run["plan"]], ["q01", "q03", "q07"])
        self.assertEqual(run["snapshots"]["source_bank_sha256"], live_demo.BANK_SHA256)
        original = experiment_v2.banks(server)[live_demo.BANK_ID]
        article = next(a for a in original["articles"] if a["id"] == run["config"]["article_ids"][0])
        self.assertEqual(run["snapshots"]["bank"]["articles"][0]["paragraphs"], article["paragraphs"])
        self.assertEqual(run["config"]["max_tokens"], 512)
        self.assertTrue(run["config"]["strict_time"])
        self.assertFalse(run["formal"])
        self.assertEqual(run["config"]["runner_version"], experiment_v2.RUNNER_VERSION)
        self.assertTrue(run["live_demo"]["full_passage"])
        queue.submit.assert_called_once_with(experiment_v2.execute_run, run["id"], server)

    def test_retry_same_request_returns_same_run_without_new_generation(self):
        first, queue1 = self.create()
        second, queue2 = self.create()
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["reused"])
        self.assertEqual(len(server.all_objects("run")), 1)
        self.assertEqual(queue1.submit.call_count, 1)
        self.assertEqual(queue2.submit.call_count, 0)
        # A completed run also remains the same immutable response to that key.
        run = server.get("run", first["id"])
        run["status"] = "completed"
        server.put("run", run["id"], run)
        third, queue3 = self.create()
        self.assertEqual(third["id"], first["id"])
        self.assertEqual(queue3.submit.call_count, 0)

    def test_key_reuse_with_different_selection_is_rejected(self):
        self.create()
        with self.assertRaisesRegex(ValueError, "不同模型或预设"):
            self.create(preset_id="en-quick")
        self.assertEqual(len(server.all_objects("run")), 1)

    def test_unrelated_activity_prevents_demo_queueing(self):
        server.put("run", "run-fixture00000", {"id": "run-fixture00000", "status": "running"})
        with patch.object(server, "request_json", return_value=self.tags):
            value = live_demo.status(server)
        self.assertEqual(value["status"], "busy")
        self.assertFalse(value["ready"])
        self.assertEqual(value["active_run"]["id"], "run-fixture00000")
        with self.assertRaisesRegex(ValueError, "已有活动实验"):
            self.create()

    def test_fixed_settings_and_explicit_draft_ack_are_enforced(self):
        for payload in ({"allow_draft": False}, {"allow_draft": 1}, {"client_request_id": ""},
                        {"max_tokens": 1}, {"bank_id": "another-bank"}, {"request_id": "inconsistent-key"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.create(**payload)
        self.assertEqual(server.all_objects("run"), [])

    def test_concurrent_duplicate_posts_create_only_one_run(self):
        with patch.object(server, "request_json", return_value=self.tags), patch.object(server, "QUEUE", Mock()) as queue:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: live_demo.create_run(copy.deepcopy(self.payload), server), range(2)))
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(sum(not result["reused"] for result in results), 1)
        self.assertEqual(queue.submit.call_count, 1)

    def test_http_api_auth_origin_create_retry_and_standard_run_fetch(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(httpd.server_port)

        def call(path, body=None, **headers):
            request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                             headers={"Content-Type": "application/json", **headers})
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.load(response)

        try:
            with patch.object(server, "TOKEN", "test-only-access"), \
                 patch.object(server, "request_json", return_value=self.tags), patch.object(server, "QUEUE", Mock()):
                with self.assertRaises(urllib.error.HTTPError) as unauthorized:
                    call("/api/demo/status")
                self.assertEqual(unauthorized.exception.code, 401)
                headers = {"Authorization": "Bearer test-only-access"}
                status_code, status = call("/api/demo/status", **headers)
                self.assertEqual(status_code, 200)
                self.assertTrue(status["ready"])
                with self.assertRaises(urllib.error.HTTPError) as cross_origin:
                    call("/api/demo/runs", self.payload, Origin="https://outside.example", **headers)
                self.assertEqual(cross_origin.exception.code, 403)
                code, created = call("/api/demo/runs", self.payload, **headers)
                self.assertEqual(code, 201)
                code, retried = call("/api/demo/runs", self.payload, **headers)
                self.assertEqual(code, 200)
                self.assertEqual(retried["id"], created["id"])
                _, standard = call("/api/v2/runs/" + created["id"], **headers)
                self.assertEqual(standard["progress"]["total"], 3)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
