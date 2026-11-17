"""Critical v2 metric checks. These constructed responses are not model runs."""
import hashlib
import unittest

from backend.benchmark_v2 import evaluate, grade, short_token_f1, validate_bank


class MetricV2Contract(unittest.TestCase):
    def setUp(self):
        self.ids = ["a:p001", "a:p002", "a:p003"]
        self.q = {"id": "q", "dimension": "D3", "kind": "short", "prompt": "谁高于谁？",
                  "answers": ["甲高于乙"], "evidence_sets": [["a:p001", "a:p002"], ["a:p003"]],
                  "reasoning_steps": ["连接两项比较关系"]}
        self.response = {"answer": "甲高于乙", "evidence_ids": ["a:p001", "a:p002"], "abstain": False, "confidence": .8}

    def test_correct_answer_requires_complete_evidence(self):
        self.assertEqual(grade(self.q, self.response, self.ids)["joint_success"], 1)
        wrong_order = grade(self.q, {**self.response, "answer": "乙高于甲"}, self.ids)
        self.assertEqual(wrong_order["answer_correct"], 0)
        for support in [["a:p001"], ["a:p001", "a:p002", "a:p003"], ["unknown"]]:
            row = grade(self.q, {**self.response, "evidence_ids": support}, self.ids)
            self.assertEqual(row["answer_correct"], 1)
            self.assertEqual(row["joint_success"], 0)
        self.assertEqual(grade(self.q, {**self.response, "evidence_ids": ["a:p003"]}, self.ids)["joint_success"], 1)

    def test_numeric_sign_unit_and_tolerance_are_explicit(self):
        q = {**self.q, "kind": "numeric", "dimension": "D4", "value": "-3", "unit": "%", "absolute_tolerance": "0.01", "operation": "difference"}
        self.assertEqual(grade(q, {**self.response, "answer": "−3.005", "unit": "%"}, self.ids)["answer_correct"], 1)
        for answer, unit in [("3", "%"), ("-3", ""), ("-3%", "%"), ("-3.02", "%")]:
            self.assertEqual(grade(q, {**self.response, "answer": answer, "unit": unit}, self.ids)["answer_correct"], 0)
            self.assertEqual(grade(q, {**self.response, "answer": answer, "unit": unit}, self.ids)["numeric_strict_accuracy"], 0)

    def test_overlap_f1_cannot_replace_strict_correctness_or_brier(self):
        swapped = grade({**self.q, "language": "zh"}, {**self.response, "answer": "乙高于甲"}, self.ids)
        self.assertEqual((swapped["short_em"], swapped["short_token_f1"], swapped["joint_success"]), (0, 1, 0))
        self.assertAlmostEqual(swapped["brier_answer"], .64)
        q = {**self.q, "answers": ["the launch was successful"], "language": "en"}
        negated = grade(q, {**self.response, "answer": "the launch was not successful"}, self.ids)
        self.assertEqual(negated["answer_correct"], 0)
        self.assertAlmostEqual(negated["short_token_f1"], 8 / 9)

    def test_f1_multisets_aliases_punctuation_and_language_are_explicit(self):
        self.assertAlmostEqual(short_token_f1("red red red blue", ["red blue"], "en"), 2 / 3)
        q = {**self.q, "language": "en", "answers": ["London", "New York"]}
        row = grade(q, {**self.response, "answer": "NEW YORK!"}, self.ids)
        self.assertEqual((row["short_em"], row["short_token_f1"]), (0, 1))
        self.assertEqual(short_token_f1("!!!", ["???"], "en"), 0)
        self.assertAlmostEqual(short_token_f1("甲乙", ["甲"], "zh"), 2 / 3)
        self.assertAlmostEqual(short_token_f1("AI甲乙 AI", ["AI甲"], "zh"), 2 / 3)
        # English words do not silently switch to the Chinese character protocol.
        self.assertEqual(short_token_f1("甲乙", ["甲"], "en"), 0)

    def test_choice_label_is_strict_and_errors_keep_kind_denominator(self):
        bank = self.bank()
        article = bank["articles"][0]
        bank["articles"] = [article]
        article["questions"] = article["questions"][:2]
        good = {"model_id": "m", "article_id": "zh", "question_id": "D1",
                "response": {"answer": "A", "evidence_ids": ["zh:p001"], "abstain": False}}
        invalid_case = {**good, "model_id": "lower", "response": {**good["response"], "answer": "a"}}
        out = evaluate(bank, [good, invalid_case], ["m", "lower", "missing"], True, 30)
        for model, expected in [("m", .5), ("lower", 0), ("missing", 0)]:
            summary = out["summaries"][model]["zh"]
            self.assertEqual(summary["primary_metrics"]["choice_accuracy"], expected)
            self.assertEqual(summary["by_question_kind"]["choice"]["planned_questions"], 2)
            self.assertIsNone(summary["primary_metrics"]["short_em"])
            self.assertIsNone(summary["grounded_understanding"])
        ci = out["statistics"]["languages"]["zh"]
        self.assertIsNone(ci["score_intervals"]["m"])
        self.assertEqual(ci["primary_metric_intervals"]["m"]["choice_accuracy"]["effective_resamples"], 30)
        self.assertEqual(ci["primary_paired_difference_intervals"]["m minus missing"]["choice_accuracy"]["lower"], .5)
        self.assertIsNone(ci["primary_metric_intervals"]["m"]["numeric_strict_accuracy"])

    def test_paired_bootstrap_reuses_source_clusters_and_preserves_identical_models(self):
        bank = self.bank()
        base = bank["articles"][0]
        bank["articles"] = []
        records = []
        for i in range(4):
            aid = f"c{i}"
            q = {**base["questions"][0], "evidence_sets": [[aid + ":p001"]]}
            a = {**base, "id": aid, "source_cluster_id": "cluster_" + str(i // 2),
                 "paragraphs": [{"id": aid + ":p001", "text": base["paragraphs"][0]["text"]}], "questions": [q]}
            bank["articles"].append(a)
            for model in ["a", "b"]:
                records.append({"model_id": model, "article_id": aid, "question_id": "D1",
                                "response": {"answer": "A" if i < 2 else "B", "evidence_ids": [aid + ":p001"], "abstain": False}})
        out = evaluate(bank, records, ["a", "b"], True, 50)
        stats = out["statistics"]["languages"]["zh"]
        self.assertEqual(stats["clusters"], 2)
        delta = stats["primary_paired_difference_intervals"]["a minus b"]["choice_accuracy"]
        self.assertEqual((delta["lower"], delta["upper"], delta["effective_resamples"]), (0, 0, 50))
        self.assertEqual(out["summaries"]["a"]["zh"]["primary_metrics"]["choice_accuracy"], .5)

    def bank(self):
        articles = []
        for language in ["zh", "en"]:
            aid = language
            text = "Immutable test passage."
            qs = [{"id": d, "dimension": d, "kind": "choice", "prompt": "Constructed scorer input?",
                   "options": {"A": "yes", "B": "no"}, "correct_option": "A", "evidence_sets": [[aid + ":p001"]],
                   "reasoning_steps": ["Scorer fixture only"], "operation": "Scorer fixture only"} for d in ["D1", "D2", "D3", "D4", "D5"]]
            qs.append({"id": "D6", "dimension": "D6", "kind": "unanswerable", "prompt": "Not supplied?", "evidence_sets": [], "missing_information": "Not in fixture"})
            articles.append({"id": aid, "language": language, "source_cluster_id": aid, "split": "development", "domain": "fixture", "length_bin": "fixture", "annotation_state": "candidate",
                             "paragraphs": [{"id": aid + ":p001", "text": text}], "presented_text_sha256": hashlib.sha256(text.encode()).hexdigest(), "questions": qs})
        return {"schema_version": "reading-bank-v2", "articles": articles}

    def test_all_refusal_and_missing_outputs_do_not_win(self):
        bank = self.bank()
        records = []
        for a in bank["articles"]:
            for q in a["questions"]:
                records.append({"model_id": "refuse", "article_id": a["id"], "question_id": q["id"], "response": {"answer": "", "abstain": True, "evidence_ids": [], "confidence": None}})
                records.append({"model_id": "answer", "article_id": a["id"], "question_id": q["id"], "response": {"answer": "A", "abstain": False, "evidence_ids": [a["id"] + ":p001"], "confidence": None}})
        out = evaluate(bank, records, ["refuse", "answer", "missing"], True, 10)
        self.assertFalse(out["formal"])
        for lang in ["zh", "en"]:
            refuse = out["summaries"]["refuse"][lang]
            answer = out["summaries"]["answer"][lang]
            missing = out["summaries"]["missing"][lang]
            self.assertEqual((refuse["grounded_understanding"], refuse["balanced_answerability"]), (0, .5))
            self.assertEqual((answer["grounded_understanding"], answer["balanced_answerability"]), (1, .5))
            self.assertEqual((missing["grounded_understanding"], missing["balanced_answerability"], missing["errors"]), (0, 0, 6))
            self.assertEqual(out["statistics"]["languages"][lang]["paired_difference_intervals"]["refuse minus answer"]["upper"], -1)

    def test_drafts_duplicates_and_corrupted_text_cannot_be_formal(self):
        bank = self.bank()
        with self.assertRaisesRegex(ValueError, "Non-frozen"):
            validate_bank(bank)
        bank["articles"][0]["paragraphs"][0]["text"] += "changed"
        with self.assertRaisesRegex(ValueError, "hash"):
            validate_bank(bank, True)
        bank = self.bank()
        r = {"model_id": "m", "article_id": "zh", "question_id": "D1", "error": "timeout"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate(bank, [r, r], ["m"], True, 0)

    def test_brier_label_is_answer_not_joint(self):
        row = grade(self.q, {**self.response, "evidence_ids": []}, self.ids)
        self.assertEqual((row["answer_correct"], row["joint_success"]), (1, 0))
        self.assertAlmostEqual(row["brier_answer"], .04)


if __name__ == "__main__":
    unittest.main()
