import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from backend.corpus_workspace import workspace_article, workspace_summary


class CandidateWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pool = self.root / "data/candidates/pool"
        (self.pool / "snapshots").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, captures):
        (self.pool / "source-discovery.json").write_text(json.dumps({"captures": captures}), encoding="utf-8")

    def test_legacy_reviewed_does_not_promote_candidates_and_duplicate_body_is_one_article(self):
        text = "事实与证据。\n\n仍需人工审查。"
        target = self.pool / "snapshots/a.txt"
        target.write_text(text + "\n", encoding="utf-8")
        record = {"id": "a", "language": "zh", "title": "待审文章", "text_path": target.relative_to(self.root).as_posix(), "sha256": hashlib.sha256(text.encode()).hexdigest(), "reviewed": True}
        self.write_manifest([record, {**record, "id": "duplicate"}])
        summary = workspace_summary(self.root)
        self.assertEqual(summary["counts"]["total"], 1)
        self.assertEqual(summary["counts"]["states"]["candidate"], 1)
        self.assertEqual(summary["counts"]["states"]["human_reviewed"], 0)
        self.assertEqual(summary["counts"]["runnable"], 0)
        self.assertNotIn("text", summary["articles"][0])
        self.assertEqual(workspace_article("a", self.root)["text"], text)

    def test_body_path_escape_and_hash_corruption_are_refused(self):
        outside = self.root / "private.txt"
        outside.write_text("private", encoding="utf-8")
        record = {"id": "bad", "text_path": "data/candidates/../../private.txt", "sha256": hashlib.sha256(b"private").hexdigest()}
        self.write_manifest([record])
        with self.assertRaisesRegex(ValueError, "路径"):
            workspace_article("bad", self.root)
        safe = self.pool / "snapshots/safe.txt"
        safe.write_text("changed", encoding="utf-8")
        self.write_manifest([{**record, "text_path": safe.relative_to(self.root).as_posix()}])
        with self.assertRaisesRegex(ValueError, "hash"):
            workspace_article("bad", self.root)
        self.assertEqual(workspace_summary(self.root)["counts"]["downloaded"], 0)

    def test_reference_passages_and_union_views_do_not_inflate_authoring_progress(self):
        folder = self.root / "data/annotation"
        folder.mkdir(parents=True)
        article = {"id": "recent", "source_cluster_id": "source", "language": "zh",
                   "paragraphs": [{"id": "recent:p001", "text": "source text"}],
                   "questions": [{"id": "q01"}], "annotation_state": "ai_checked"}
        bank = {"schema_version": "reading-bank-v2", "articles": [article]}
        (folder / "recent.json").write_text(json.dumps(bank), encoding="utf-8")
        (folder / "union.json").write_text(json.dumps({**bank, "collection_view": True}), encoding="utf-8")
        (folder / "reference.json").write_text(json.dumps({**bank, "annotation_origin": "external_public_benchmark",
            "articles": [{**article, "id": "reference", "source_cluster_id": "reference-title"}]}), encoding="utf-8")
        summary = workspace_summary(self.root)
        self.assertEqual(summary["annotation_counts"]["articles"], 1)
        self.assertEqual(summary["annotation_counts"]["questions"], 1)
        self.assertEqual(len(summary["annotation_workspaces"]), 1)


if __name__ == "__main__":
    unittest.main()
