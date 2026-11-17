"""Compare synthetic numeric edits to sealed original-passage runs.

Small, descriptive diagnostic only. No contamination or population ranking
claim can be inferred from five cases per language.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from backend.benchmark_v2 import validate_bank
from scripts.run_model_matrix import assert_run_identity, digest
from scripts.summarize_model_matrix import checked_rows, check_csv, inventory, read_json, contained_path as safe_artifact, sha_file, model_label, original_bank

def numeric_equal(answer: str | None, expected: str) -> bool:
    try:
        return answer is not None and Decimal(answer) == Decimal(expected)
    except (InvalidOperation, ValueError, TypeError):
        return False

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-dirs", type=Path, nargs="+", required=True)
    parser.add_argument("--counterfactual-dirs", "--counterfactual-dir", type=Path, nargs="+", required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    main_audit = inventory(args.main_dirs, args.models)
    if not main_audit["complete"]:
        raise ValueError("Original main/control matrices are incomplete")
    original = {(r["model_id"], r["article_id"], r["question_id"]): r for r in main_audit["rows"] if r["mode"] == "with_context"}
    cases, artifacts = [], []
    for directory in args.counterfactual_dirs:
        manifest_path = directory / "manifest.json"
        manifest = read_json(manifest_path)
        if manifest["specification"]["modes"] != ["with_context"] or not set(manifest["models"]).issubset(args.models):
            raise ValueError("Counterfactual model/mode plan mismatch")
        source = manifest["source_bank_operator_snapshot"]
        undecorated = original_bank(source)
        validate_bank(undecorated, allow_draft=True)
        if digest(undecorated) != manifest["source_bank_sha256"] or digest(manifest["selection"]) != manifest["selection_sha256"]:
            raise ValueError("Synthetic source or selection hash mismatch")
        if not source.get("synthetic") or not source.get("diagnostic_only") or len(source["articles"]) != 10:
            raise ValueError("Expected the explicitly synthetic ten-case diagnostic")
        if Counter(a["language"] for a in source["articles"]) != {"zh": 5, "en": 5}:
            raise ValueError("Expected five cases per language")
        artifacts.append({"path": str(manifest_path.resolve()), "sha256": sha_file(manifest_path)})
        for job in manifest["jobs"]:
            if job.get("status") != "exported" or not job.get("complete"):
                raise ValueError("Counterfactual job is incomplete")
            run_path = safe_artifact(directory, job["json"])
            csv_path = safe_artifact(directory, job["csv"])
            if sha_file(run_path) != job["json_file_sha256"] or sha_file(csv_path) != job["csv_file_sha256"]:
                raise ValueError("Counterfactual export hash mismatch")
            run = read_json(run_path)
            assert_run_identity(run, job, manifest)
            check_csv(csv_path, run)
            if len(run["plan"]) != 10 or len(run["results"]) != 10:
                raise ValueError("Counterfactual run is incomplete")
            articles = {a["id"]: a for a in run["snapshots"]["bank"]["articles"]}
            for row in checked_rows(run):
                article = articles[row["article_id"]]
                edit = article["counterfactual_edit"]
                before = original[(row["model_id"], article["derived_from_article_id"], edit["original_question_id"])]
                if (article["original_presented_text_sha256"] != before["article_sha256"] or
                    row["source_cluster_id"] != before["source_cluster_id"] or
                    edit["old_gold"] != before["frozen_question"]["value"] or
                    edit["new_gold"] != row["frozen_question"]["value"] or
                    row["frozen_question"]["prompt"] != before["frozen_question"]["prompt"]):
                    raise ValueError("Synthetic/original question mapping disagrees")
                response = row.get("response") or {}
                cases.append({"model_id": row["model_id"], "language": row["language"], "source_cluster_id": row["source_cluster_id"], "original_run_id": before["run_id"], "counterfactual_run_id": row["run_id"], "article_id": row["article_id"], "question_id": row["question_id"], "old_gold": edit["old_gold"], "new_gold": edit["new_gold"], "original_strict_success": before["metrics"]["answer_correct"], "modified_strict_success": row["metrics"]["answer_correct"], "modified_numeric_value_matches_new_aux": int(numeric_equal(response.get("answer"), edit["new_gold"])), "modified_numeric_value_matches_old_aux": int(numeric_equal(response.get("answer"), edit["old_gold"])), "response_error": row.get("error"), "raw_response": row["raw_response"], "response": response})
            artifacts.extend({"path": str(path.resolve()), "sha256": sha_file(path)} for path in (run_path, csv_path))
    expected = len(args.models) * 10
    if len(cases) != expected or len({(c["model_id"], c["article_id"], c["question_id"]) for c in cases}) != expected:
        raise ValueError("Missing or duplicate counterfactual case")
    summary = []
    for model in args.models:
        for language in ("zh", "en"):
            group = [c for c in cases if (c["model_id"], c["language"]) == (model, language)]
            summary.append({"model_id": model, "language": language, "cases": len(group), "original_strict_correct": sum(c["original_strict_success"] for c in group), "modified_strict_correct": sum(c["modified_strict_success"] for c in group), "both_original_and_modified_correct": sum(c["original_strict_success"] and c["modified_strict_success"] for c in group), "modified_numeric_value_matches_new_aux": sum(c["modified_numeric_value_matches_new_aux"] for c in group), "modified_numeric_value_matches_old_aux": sum(c["modified_numeric_value_matches_old_aux"] for c in group), "response_errors": sum(bool(c["response_error"]) for c in group)})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {"formal": False, "synthetic": True, "human_review_count": 0, "models": args.models, "cases_per_language": 5, "requests": len(cases), "source_bank_sha256": main_audit["source_bank_sha256"], "provenance": artifacts, "original_artifacts": main_audit["artifacts"], "summary": summary, "cases": cases, "limitations": ["Five hand-selected synthetic cases per language, not independent new articles.", "Descriptive counts only; one seed, no hypothesis tests or formal model ranking.", "Correctly following edited text supports local text sensitivity, not absence of training contamination.", "Numeric-value-only columns are auxiliary; strict score still requires the frozen unit and response contract."]}
    (args.output_dir / "counterfactual-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "counterfactual-summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    lines = ["# 合成改文诊断", "", "10个合成数字改文案例（中英各5），逐模型与同题原文主实验配对。合成材料不代表来源网站真实报道，不计作新增文章，不与主实验指标合并。人工审题0。", "", "| 模型 | 语言 | 原文严格正确 | 改文严格正确 | 两次均正确 | 改文数值跟随新值（辅助） | 改文仍答旧值（辅助） |", "|---|---|---:|---:|---:|---:|---:|"]
    for s in summary:
        lines.append(f"| {model_label(s['model_id'])} | {s['language']} | {s['original_strict_correct']}/5 | {s['modified_strict_correct']}/5 | {s['both_original_and_modified_correct']}/5 | {s['modified_numeric_value_matches_new_aux']}/5 | {s['modified_numeric_value_matches_old_aux']}/5 |")
    lines += ["", "严格正确包含数值、单位和合法输出契约。数值辅助列只查看合法解析回答中的数值，不能替代严格成绩；格式失败保留在总分母。样本仅5题/语言，不进行显著性检验、不宣称总体稳定性或无训练污染。全部改文映射、原始回答及hash见counterfactual-results.json。", ""]
    (args.output_dir / "counterfactual-report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"requests": len(cases), "output": str(args.output_dir), "formal": False}))

if __name__ == "__main__":
    main()
