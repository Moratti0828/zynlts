"""Post-hoc sensitivity diagnostic; never changes sealed primary scores.

Maps only whitespace, one surrounding square-bracket pair, and an unambiguous
article-local pNNN identifier. No gold selection, passage retrieval, semantic
rewriting, extra-ID removal or failed-response repair is performed.
"""
from __future__ import annotations
import argparse
import copy
import csv
import json
from pathlib import Path
import re

from backend import benchmark_v2 as scorer
from scripts.summarize_model_matrix import inventory, model_label

def normalize_id(value: str, article_id: str, known: set[str]) -> str:
    normalized = value.strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    if re.fullmatch(r"p\d{3}", normalized):
        normalized = article_id + ":" + normalized
    return normalized if normalized in known else value

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-dirs", nargs="+", type=Path, required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit = inventory(args.matrix_dirs, args.models)
    if not audit["complete"]:
        raise ValueError("Main matrices incomplete")
    article_map = {a["id"]: a for a in audit["bank"]["articles"]}
    counts, cases = [], []
    for model in args.models:
        for language in ("zh", "en"):
            rows = [r for r in audit["rows"] if r["model_id"] == model and r["mode"] == "with_context" and r["language"] == language and r["kind"] != "unanswerable"]
            strict, diagnostic, changed, duplicate_mapping = 0, 0, 0, 0
            for row in rows:
                primary = row["metrics"]["evidence_exact"]
                strict += primary
                normalized_score = primary
                response = row.get("response")
                if not row.get("error") and response:
                    known = {p["id"] for p in article_map[row["article_id"]]["paragraphs"]}
                    ids = [normalize_id(i, row["article_id"], known) for i in response["evidence_ids"]]
                    # Preserve invalid multiplicity; do not silently drop IDs.
                    if len(ids) != len(set(ids)):
                        duplicate_mapping += 1
                    elif ids != response["evidence_ids"]:
                        changed += 1
                        normalized = copy.deepcopy(response)
                        normalized["evidence_ids"] = ids
                        normalized_score = scorer.grade(row["frozen_question"], normalized, list(known), language=language)["evidence_exact"]
                        cases.append({"run_id": row["run_id"], "model_id": model, "language": language, "article_id": row["article_id"], "question_id": row["question_id"], "raw_ids": response["evidence_ids"], "normalized_ids": ids, "strict_evidence_exact": primary, "diagnostic_evidence_exact": normalized_score})
                diagnostic += normalized_score
            counts.append({"model_id": model, "language": language, "planned_answerable": len(rows), "strict_exact_n": strict, "format_normalized_exact_n_aux": diagnostic, "difference_n_aux": diagnostic - strict, "mapped_response_n": changed, "duplicate_mapping_unchanged_n": duplicate_mapping})
    result = {"diagnostic_only": True, "post_hoc": True, "primary_scores_changed": False, "human_review_count": 0, "normalization_policy": normalize_id.__doc__ or __doc__, "source_bank_sha256": audit["source_bank_sha256"], "source_artifacts": audit["artifacts"], "counts": counts, "mapped_cases": cases, "limitations": "This post-hoc format sensitivity check is not a new reading ranking or a correction to archived scores. All original planned failures remain failures; semantic evidence errors remain errors."}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evidence-id-diagnostic.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "evidence-id-diagnostic.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(counts[0]));writer.writeheader();writer.writerows(counts)
    lines = ["# 证据ID格式敏感性诊断", "", "这是查看结果后增加、统一应用于全部模型的辅助诊断，不修改已冻结主成绩。只去首尾空白、单层方括号，并把在本篇中唯一对应的pNNN补成完整ID。不得猜选段落、删掉多引证据、修复格式失败响应或改金标。", "", "| 模型 | 语言 | 严格证据EM | 仅格式归一化后（辅助） | 仅格式造成的差额 |", "|---|---|---:|---:|---:|"]
    for row in counts:
        n = row["planned_answerable"]
        lines.append(f"| {model_label(row['model_id'])} | {row['language']} | {row['strict_exact_n']}/{n} | {row['format_normalized_exact_n_aux']}/{n} | {row['difference_n_aux']}题 |")
    lines += ["", "辅助列用来判断输出ID写法对严格证据分数的影响，不能替代主实验指标或据此挑选最好成绩。下一版协议应预先设计更清晰的段落编号/引用契约，重新冻结题库与评分版本后验证。", ""]
    (args.output_dir / "evidence-id-diagnostic.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"records": len(counts), "primary_scores_changed": False, "output": str(args.output_dir)}))

if __name__ == "__main__":
    main()
