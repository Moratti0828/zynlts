"""Freeze ten synthetic numeric edits to diagnose following provided text.

This derived diagnostic is explicitly fictional and never joins the real-news
main benchmark. Original questions/gold and original run records stay unchanged.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path

from backend.benchmark_v2 import validate_bank

ROOT = Path(__file__).resolve().parents[1]
EDITS = [
    ("zh-nbs-02a36a9fc6f8", "q01", "327569", "427569", "427569"),
    ("zh-nbs-d8dd3b95e0c6", "q01", "5963.4", "6963.4", "6963.4"),
    ("zh-cas_health-d9258d90ea32", "q01", "300天", "420天", "420"),
    ("zh-cas_health-31517790bbba", "q02", "第98位", "第97位", "97"),
    ("zh-mct-2310a232a3eb", "q01", "30000元", "33000元", "33000"),
    ("en-census-be20ba82c0cc", "q01", "87,460", "96,460", "96460"),
    ("en-nih-63b73a8c608a", "q01", "15,809", "16,809", "16809"),
    ("en-loc-829b92bd1e91", "q02", "$150,000", "$175,000", "175000"),
    ("en-usgs_release-8091ff19244f", "q02", "next two years", "next three years", "3"),
    ("en-govuk-d5865b812982", "q01", "£100 million", "£120 million", "120"),
]

def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def main() -> None:
    original = ROOT / "data/annotation/dev-expanded-20261020.json"
    bank = json.loads(original.read_bytes())
    articles = []
    for cluster, qid, old, new, value in EDITS:
        source = next(a for a in bank["articles"] if a["source_cluster_id"] == cluster)
        article = copy.deepcopy(source)
        old_id = article["id"]
        article["id"] += "-cf"
        article["title"] = "[SYNTHETIC DIAGNOSTIC / 合成改文] " + article["title"]
        changes = []
        for paragraph in article["paragraphs"]:
            paragraph["id"] = paragraph["id"].replace(old_id + ":p", article["id"] + ":p")
            count = paragraph["text"].count(old)
            if count:
                paragraph["text"] = paragraph["text"].replace(old, new)
                changes.append({"paragraph_id": paragraph["id"], "occurrences": count})
        if not changes:
            raise ValueError("No exact synthetic-edit target: " + cluster)
        question = copy.deepcopy(next(q for q in source["questions"] if q["id"] == qid))
        if question["kind"] != "numeric" or question["value"] == value:
            raise ValueError("Counterfactual requires a changed numeric gold")
        before = question["value"]
        question["value"] = value
        question["evidence_sets"] = [[p.replace(old_id + ":p", article["id"] + ":p") for p in support] for support in question["evidence_sets"]]
        article["questions"] = [question]
        article["scope"] = "synthetic_counterfactual"
        article["scope_note"] = "合成改文，仅用于跟随给定文本的诊断；不代表来源网站真实报道，不计入主题库文章数量。"
        article["synthetic"] = True
        article["derived_from_article_id"] = old_id
        article["original_presented_text_sha256"] = source["presented_text_sha256"]
        article["counterfactual_edit"] = {"old_literal": old, "new_literal": new, "old_gold": before, "new_gold": value, "changes": changes, "original_question_id": qid, "instruction_policy": "same task instruction and question; edited passage only"}
        article["presented_text_sha256"] = sha("\n\n".join(p["text"] for p in article["paragraphs"]).encode())
        article["ai_source_audit"] = {"date": "2026-10-20", "status": "mechanically_derived_numeric_diagnostic", "human_review": False, "model_outputs_consulted": False}
        articles.append(article)
    derived = {"schema_version": "reading-bank-v2", "bank_version": "counterfactual-20261020", "formal": False, "diagnostic_only": True, "synthetic": True, "human_review_count": 0, "note": "10个合成数字改文诊断（中英各5），原始文章来源仍只有20篇；与同题原文主实验配对，检查跟随文本变化，不是新闻事实测评或无污染证明。", "source_bank_file_sha256": sha(original.read_bytes()), "articles": articles}
    validate_bank(derived, allow_draft=True)
    target = ROOT / "data/diagnostics/dev-counterfactual-20261020.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(derived, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"file": str(target), "articles": 10, "questions": 10, "languages": {"zh": 5, "en": 5}, "synthetic": True, "file_sha256": sha(target.read_bytes())}))

if __name__ == "__main__":
    main()
