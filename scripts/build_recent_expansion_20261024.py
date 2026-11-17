"""Build and validate a separate recent development bank without model calls.

Presentation scopes and questions were source-read on 2026-10-24. The completed
bank is mechanically validated on 2026-10-25. Human review remains exactly zero.
Existing source captures, old banks and archived runs are read-only inputs.
"""
from __future__ import annotations

from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import re

from backend.benchmark_v2 import grade, validate_bank
from backend.corpus_workspace import _body, _records
from backend.experiment_v2 import messages
from backend.token_budget import prepare_budget
from scripts.recent_expansion_items_20261024 import ITEMS

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "data/annotation/dev-recent-additions-20261024.json"
CHECKS = ROOT / "output/recent-expansion-validation-20261024.json"
AUDIT = ROOT / "docs/recent-expansion-audit-20261024.md"
OLD = ROOT / "data/annotation/dev-expanded-20261020.json"
SCOPE_DATE = "2026-10-24"
VERIFICATION_DATE = "2026-10-25"

# Balance answer positions before freezing or exposing this bank to any model.
# A separate fixed RNG permutes the target positions across questions, then
# each question's non-correct alternatives are independently permuted.
_choice_keys = [(i["source"], n) for i in ITEMS for n, q in enumerate(i["questions"], 1)
                if q["kind"] == "choice"]
_targets = ["ABCD"[n % 4] for n in range(len(_choice_keys))]
random.Random(20261024).shuffle(_targets)
CHOICE_TARGETS = dict(zip(_choice_keys, _targets))


def sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def canonical_sha(value: object) -> str:
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def owned_source_file(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to((ROOT / "data/candidates").resolve()) or not path.is_file():
        raise ValueError("Source file must exist inside the candidate directory")
    return path


def make_article(specification: dict, source: dict) -> tuple[dict, dict]:
    body = _body(source, ROOT)
    assert body == source["text"], "Capture body disagrees with its manifest"
    raw = owned_source_file(source["raw_path"])
    assert sha(raw.read_bytes()) == source["raw_sha256"], "Raw source hash mismatch"
    original = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    start, end = specification["start"], specification["end"]
    assert start == 1 and start <= end <= len(original)
    aid = source["id"] + "-dev20261024"
    paragraphs = [{"id": f"{aid}:p{number:03d}", "text": original[index - 1],
                   "source_paragraph_index": index}
                  for number, index in enumerate(range(start, end + 1), 1)]
    qs = []
    for number, authored in enumerate(specification["questions"], 1):
        q = copy.deepcopy(authored)
        support = q.pop("support")
        alternatives = q.pop("support_alternatives", [])
        chains = [support, *alternatives] if support else []
        assert len({tuple(chain) for chain in chains}) == len(chains)
        qid = f"q{number:02d}"
        if q["kind"] == "choice":
            # Pre-run, outcome-independent option order; do not retain a fixed
            # correct-letter pattern from source authoring.
            old_keys = list(q["options"])
            rng = random.Random(int(sha(aid + "/" + qid + "/20261024")[:16], 16))
            rng.shuffle(old_keys)
            correct_original = q["correct_option"]
            correct_target = CHOICE_TARGETS[(specification["source"], number)]
            mapping = {correct_original: correct_target}
            remaining_targets = [label for label in "ABCD" if label != correct_target]
            mapping.update(zip((label for label in old_keys if label != correct_original), remaining_targets))
            permuted = {mapping[key]: q["options"][key] for key in old_keys}
            q["options"] = {label: permuted[label] for label in "ABCD"}
            q["correct_option"] = mapping[q["correct_option"]]
            q["option_order_policy"] = "pre-run balanced correct letters (A16/B15/C15/D15), seed20261024 target permutation; SHA-seeded distractor order"
            q["authored_to_presented_option_mapping"] = mapping
        q.update(id=qid,
                 evidence_sets=[[paragraphs[n - 1]["id"] for n in chain] for chain in chains],
                 annotation_state="ai_checked", human_review_count=0, human_reviews=[],
                 adjudication_complete=False, generator="Codex source-read authoring; selection 2026-10-24",
                 training_seen_status="unknown", answer_novelty_review_state="pending_human_review")
        qs.append(q)
    actual_scope = "full" if end == len(original) else "excerpt"
    scope_note = (f"预先固定连续原段{start}—{end}；共{len(original)}个原段。"
                  "未按模型输出或答案抽取碎片；未呈现的后续段落不属于作答材料。"
                  if actual_scope == "excerpt" else
                  f"完整正文{start}—{end}段，保留原顺序及图注文字，图片本身不呈现。")
    article = {
        "id": aid, "title": source["title"], "language": source["language"],
        "source_cluster_id": source["id"], "source_cluster_reviewed": False,
        "proposed_source_cluster": source["id"], "source_url": source["source_url"],
        "source_name": source["source_name"], "agency_group": source["provider"],
        "published_at": source["published_at"], "first_published_at": source.get("first_published_at"),
        "date_evidence": source.get("date_evidence"), "date_review_note": source.get("date_review_note"),
        "rights": source["rights"], "source_text_sha256": source["sha256"],
        "source_raw_sha256": source["raw_sha256"], "source_raw_path": source["raw_path"],
        "source_text_path": source["text_path"], "scope": actual_scope, "scope_note": scope_note,
        "scope_declared_before_question_authoring": "scope_revision_reason" not in specification,
        "scope_declared_before_model_testing": True, "scope_declared_on": SCOPE_DATE,
        "scope_finalized_on": VERIFICATION_DATE,
        "scope_revision_reason": specification.get("scope_revision_reason"),
        "split": "development", "domain": specification["domain"],
        "length_bin": "short" if len(body.encode("utf-8")) < 3000 else "medium",
        "annotation_state": "ai_checked", "human_review_count": 0, "formal": False,
        "globally_earliest_publication_proven": False, "publication_date_is_answer_novelty_proof": False,
        "training_seen_status": "unknown",
        "risk_flags": ["possible_earlier_related_work_or_preprint", "older_background_knowledge",
                       "source_cluster_lineage_not_human_reviewed", "AI_authored_gold_human0"],
        "time_review_note": "2026官网正文快照；全球最早报道和每题答案新颖性尚未人审。不能据网页日期声称无训练污染。",
        "content_summary": specification["summary"], "paragraphs": paragraphs,
        "presented_text_sha256": sha("\n\n".join(p["text"] for p in paragraphs)), "questions": qs,
    }
    # Neither a repository URL timestamp nor a site update is silently promoted
    # to globally first publication. Keep URL hints separate for later review.
    url_stamp = re.search(r"(?:/|t)(20\d{6})(?:_|/|\b)", source["source_url"])
    if url_stamp:
        article["url_date_hint_unverified"] = url_stamp.group(1)
    return article, {"source_id": source["id"], "source_text_sha256": source["sha256"],
                     "source_raw_sha256": source["raw_sha256"], "source_paragraphs": len(original),
                     "presented_paragraphs": len(paragraphs), "aligned_source_indexes": list(range(start, end + 1)),
                     "body_and_raw_hash_verified": True, "contiguous_paragraph_alignment_verified": True}


def verify_operation(q: dict) -> None:
    if q["dimension"] != "D4":
        return
    op = q["operation"]
    a, b = map(Decimal, op["operands"])
    if op["type"] in {"subtract", "subtract_percentage_points", "subtract_signed_percentage_points", "subtract_minimum_target"}:
        value = a - b
    elif op["type"] == "add":
        value = a + b
    elif op["type"] == "multiply":
        value = a * b
    elif op["type"] == "divide":
        value = a / b
    else:
        raise ValueError("Unverified arithmetic operation")
    assert value == Decimal(q["value"]), (q["id"], op)


def validate(bank: dict, source_checks: list[dict]) -> dict:
    articles = validate_bank(bank, allow_draft=True)
    try:
        validate_bank(bank, allow_draft=False)
    except ValueError as exc:
        rejection = str(exc)
    else:
        raise AssertionError("AI authored bank must not pass formal admission")
    old = read_json(OLD)
    old_source_ids = {a["source_cluster_id"] for a in old["articles"]}
    old_source_hashes = {a["source_text_sha256"] for a in old["articles"]}
    assert not old_source_ids.intersection(a["source_cluster_id"] for a in articles)
    assert not old_source_hashes.intersection(a["source_text_sha256"] for a in articles)
    assert len({a["source_cluster_id"] for a in articles}) == len(articles) == 20
    assert Counter(a["language"] for a in articles) == {"zh": 10, "en": 10}
    directory = ROOT / "runtime/tokenizers/qwen25-7b-a09a354"
    manifest_path = directory / "manifest.json"
    tokenizer = read_json(manifest_path)
    qwen = {"tokenizer_spec": {"repo_id": tokenizer["repo_id"], "revision": tokenizer["revision"],
                              "artifact_dir": str(directory), "manifest_sha256": sha(manifest_path.read_bytes())},
            "runtime_template_kind": "raw_rendered_prompt", "token_budget_margin": 512}
    question_checks = []
    for article in articles:
        assert article["published_at"].startswith("2026-")
        assert article["published_at"] <= SCOPE_DATE
        assert len(article["questions"]) == 8
        assert Counter(q["kind"] for q in article["questions"])["unanswerable"] == 2
        pids = [p["id"] for p in article["paragraphs"]]
        for q in article["questions"]:
            verify_operation(q)
            is_unknown = q["kind"] == "unanswerable"
            answer = "" if is_unknown else q.get("correct_option", q.get("value", q.get("answers", [""])[0]))
            response = {"answer": answer, "unit": q.get("unit", ""),
                        "evidence_ids": [] if is_unknown else q["evidence_sets"][0],
                        "abstain": is_unknown, "confidence": 1.0}
            result = grade(q, response, pids, language=article["language"])
            assert result["answer_correct"] == 1
            if not is_unknown:
                assert result["evidence_exact"] == 1
                for support in q["evidence_sets"]:
                    assert grade(q, {**response, "evidence_ids": support}, pids,
                                 language=article["language"])["evidence_exact"] == 1
            prompt = messages(article, q, "with_context")
            exact = prepare_budget(qwen, prompt, 512, 8192, strict=True)
            estimate = prepare_budget({}, prompt, 512, 8192, strict=False)
            assert exact["allowed"], (article["id"], q["id"], exact["reason"])
            assert estimate["allowed"], (article["id"], q["id"], estimate["total_tokens"])
            question_checks.append({"article_id": article["id"], "question_id": q["id"],
                                    "language": article["language"], "kind": q["kind"], "dimension": q["dimension"],
                                    "evidence_chains": q["evidence_sets"], "reference_roundtrip_correct": True,
                                    "qwen_exact_input_tokens": exact["input_tokens"],
                                    "qwen_exact_total_tokens": exact["total_tokens"],
                                    "draft_utf8_total_bound": estimate["total_tokens"],
                                    "qwen_exact_and_draft_budget_admitted": True})
    return {"source_scope_date": SCOPE_DATE, "verified_on_client_date": VERIFICATION_DATE,
            "bank_id": bank["bank_version"], "formal": False, "human_review_count": 0,
            "counts": {"articles": 20, "questions": len(question_checks), "languages": {"zh": 10, "en": 10},
                       "questions_by_language": dict(Counter(q["language"] for q in question_checks)),
                       "question_kinds": dict(Counter(q["kind"] for q in question_checks)),
                       "dimensions": dict(Counter(q["dimension"] for q in question_checks))},
            "schema_validated": True, "formal_rejected_as_expected": rejection,
            "old_bank_sha256_unchanged": sha(OLD.read_bytes()),
            "new_source_ids_nonoverlap_with_old20": True, "new_source_text_hashes_nonoverlap_with_old20": True,
            "all_source_raw_and_body_hashes_match": True, "all_presented_paragraphs_align_to_contiguous_source": True,
            "all_qwen_exact_budgets_pass": True, "all_conservative_draft_budgets_pass": True,
            "arithmetic_gold_checked_using_decimal": True, "sources": source_checks,
            "questions": question_checks,
            "limitations": ["AI authoring and AI source read only; zero independent human review.",
                            "Reference round-trip validates scorer integration, not independent gold correctness.",
                            "Source article IDs are provisional clusters, not proven independent events.",
                            "2026 publication does not prove answer novelty or absence from model training.",
                            "Qwen2.5-7B exact tokenizer budget only; other families require separate certification."]}


def main() -> None:
    records = {record["id"]: record for record, _ in _records(ROOT)[0]}
    articles, sources = zip(*(make_article(item, records[item["source"]]) for item in ITEMS))
    bank = {"schema_version": "reading-bank-v2", "bank_version": "dev-recent-additions-20261024",
            "formal": False, "human_review_count": 0, "as_of_client_date": SCOPE_DATE,
            "built_and_validated_on_client_date": VERIFICATION_DATE,
            "target_articles": 20, "target_questions": 160,
            "note": "20篇新增2026真实来源的AI开发题稿，中英各10篇80题，人审0；不与旧20篇重复，不是正式隐藏测试或无污染证明。固定连续呈现范围及金标，不根据模型输出修改。",
            "annotation_origin": "AI_source_read_development_authoring",
            "source_selection_sha256": canonical_sha([{"source": i["source"], "start": i["start"], "end": i["end"]} for i in ITEMS]),
            "articles": list(articles)}
    bank["independent_ai_review_records"] = [
        {"language": language, "articles": 10, "questions": 80, "human_review": False,
         "path": f"docs/recent-expansion-{language}-independent-review-20261025.md",
         "sha256": sha((ROOT / f"docs/recent-expansion-{language}-independent-review-20261025.md").read_bytes())}
        for language in ("zh", "en")]
    bank["pre_run_review_resolution"] = "Eight substantive gold/premise issues fixed before any model saw this new bank; two name aliases and one explicit platform-name support alternative also added. Old experimental banks unchanged; AI review is not human review. See dated audit note."
    validation = validate(bank, list(sources))
    encoded = json.dumps(bank, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    BANK.parent.mkdir(parents=True, exist_ok=True)
    BANK.write_text(encoded, encoding="utf-8")
    validation.update(bank_file_sha256=sha(BANK.read_bytes()), bank_canonical_sha256=canonical_sha(bank),
                      authoring_items_sha256=sha((ROOT / "scripts/recent_expansion_items_20261024.py").read_bytes()),
                      audit_note_sha256=sha(AUDIT.read_bytes()))
    CHECKS.write_text(json.dumps(validation, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"bank": str(BANK), "counts": validation["counts"],
                      "bank_file_sha256": validation["bank_file_sha256"], "formal": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
