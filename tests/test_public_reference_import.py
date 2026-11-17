"""Mapping invariants for unmodified, contamination-exposed reference data."""
from __future__ import annotations

import copy
import unittest

from backend.benchmark_v2 import validate_bank
from scripts.import_public_reference_20261024 import (
    convert_passage, select_passages, verify_roundtrip, verify_spans,
)


SOURCE = {"url": "https://example.org/fixed-dev.json", "dataset_file_commit_date": "2019-03-29",
          "revision": "a" * 40, "sha256": "b" * 64, "filename": "fixture.json"}


def qa(identity: str, answer: str = "Paris", start: int = 2) -> dict:
    return {"id": identity, "question": "What is the named city?", "answers": [{"text": answer, "answer_start": start}]}


def fixture() -> dict:
    topics = []
    for title in ("Alpha", "Beta", "Gamma"):
        paragraphs = []
        for index in range(2):
            context = f"  Paris is named here. {title}-{index}.  "
            questions = [qa(f"{title}-{index}-a"), qa(f"{title}-{index}-b"), qa(f"{title}-{index}-c")]
            questions.append({"id": f"{title}-{index}-u", "question": "What is its exact annual cost?",
                              "is_impossible": True, "answers": [],
                              "plausible_answers": [{"text": "Paris", "answer_start": 2}]})
            paragraphs.append({"context": context, "qas": questions})
        topics.append({"title": title, "paragraphs": paragraphs})
    return {"data": topics}


class PublicReferenceImportTests(unittest.TestCase):
    def test_bad_official_offset_is_rejected_not_repaired(self):
        item = qa("external-q", start=0)
        with self.assertRaisesRegex(ValueError, "exact offset"):
            verify_spans("  Paris is present", item)

    def test_original_context_question_answers_and_offsets_are_unchanged(self):
        paragraph = fixture()["data"][0]["paragraphs"][0]
        original = copy.deepcopy(paragraph)
        article = convert_passage("cmrc2018", "Alpha", paragraph, 0, 0, paragraph["qas"][:3], SOURCE)
        self.assertEqual(article["paragraphs"][0]["text"], paragraph["context"])
        self.assertTrue(article["paragraphs"][0]["text"].startswith("  "))
        self.assertTrue(article["paragraphs"][0]["text"].endswith("  "))
        self.assertEqual(article["questions"][0]["prompt"], paragraph["qas"][0]["question"])
        self.assertEqual(article["questions"][0]["external_answers"], paragraph["qas"][0]["answers"])
        self.assertEqual(paragraph, original)

    def test_unanswerable_keeps_official_label_and_no_support_chain(self):
        data = fixture()
        articles, _ = select_passages("squad2", data, SOURCE, count=1)
        unknown = next(q for q in articles[0]["questions"] if q["kind"] == "unanswerable")
        self.assertTrue(unknown["external_is_impossible"])
        self.assertEqual(unknown["external_answers"], [])
        self.assertEqual(unknown["evidence_sets"], [])
        self.assertEqual(unknown["evidence_gold_status"], "not_applicable")
        bad = copy.deepcopy(unknown)
        with self.assertRaisesRegex(ValueError, "answerability"):
            verify_spans("Paris", {"id": "bad", "question": bad["prompt"], "answers": [{"text": "Paris", "answer_start": 0}], "is_impossible": True})

    def test_proxy_evidence_never_becomes_human_reviewed_gold(self):
        articles, _ = select_passages("cmrc2018", fixture(), SOURCE, count=2)
        validate_bank({"schema_version": "reading-bank-v2", "articles": articles}, allow_draft=True)
        for article in articles:
            self.assertEqual(article["human_review_count"], 0)
            self.assertFalse(article["requires_temporal_isolation"])
            self.assertEqual(article["split"], "reference")
            for item in article["questions"]:
                self.assertEqual(item["evidence_annotation_origin"], "span_derived_proxy/draft")
                self.assertEqual(item["evidence_gold_status"], "unreviewed_proxy")
        with self.assertRaisesRegex(ValueError, "Non-frozen"):
            validate_bank({"schema_version": "reading-bank-v2", "articles": articles}, allow_draft=False)

    def test_same_title_shares_cluster_and_duplicate_context_is_excluded(self):
        data = fixture()
        data["data"][1]["paragraphs"].append(copy.deepcopy(data["data"][0]["paragraphs"][0]))
        articles, stats = select_passages("cmrc2018", data, SOURCE, count=6)
        self.assertEqual(stats["duplicate_contexts_excluded"], 1)
        self.assertEqual(len({a["source_text_sha256"] for a in articles}), 6)
        alpha = [a for a in articles if a["external_source_title"] == "Alpha"]
        self.assertEqual(len(alpha), 2)
        self.assertEqual(len({a["source_cluster_id"] for a in alpha}), 1)

    def test_deterministic_sample_covers_titles_before_extra_contexts(self):
        first, _ = select_passages("squad2", fixture(), SOURCE, count=3)
        second, _ = select_passages("squad2", fixture(), SOURCE, count=3)
        self.assertEqual(first, second)
        self.assertEqual(len({a["external_source_title"] for a in first}), 3)
        self.assertTrue(all(a["mechanical_validation"]["max_conservative_total_tokens"] <= 8192 for a in first))

    def test_invalid_source_questions_are_logged_and_not_selected(self):
        data = fixture()
        bad = qa("bad-offset", start=200)
        data["data"][0]["paragraphs"][0]["qas"].append(bad)
        articles, stats = select_passages("cmrc2018", data, SOURCE, count=6)
        self.assertEqual(stats["rejected_original_question_spans"], [{"external_question_id": "bad-offset", "reason": "Official answer text does not match its exact offset"}])
        self.assertFalse(any(q["external_question_id"] == "bad-offset" for a in articles for q in a["questions"]))
        self.assertEqual(stats["answer_offset_repairs"], 0)

    def test_roundtrip_detects_rewritten_original_question(self):
        data = fixture()
        articles, _ = select_passages("cmrc2018", data, SOURCE, count=2)
        bank = {"articles": articles}
        self.assertEqual(verify_roundtrip(bank, data)["questions_checked"], 6)
        bank["articles"][0]["questions"][0]["prompt"] += " invented hint"
        with self.assertRaisesRegex(ValueError, "question/answer"):
            verify_roundtrip(bank, data)


if __name__ == "__main__":
    unittest.main()
