"""Version reference stratification before first inference, preserving raw QA."""
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
from backend import benchmark_v2 as scorer
from backend.experiment_v2 import digest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    summary = {}
    for dataset in ("squad2", "cmrc2018"):
        previous = ROOT / f"data/reference/initial-import-banks-20261024/reference-{dataset}-20261024.json"
        source = json.loads(previous.read_text(encoding="utf-8"))
        bank = copy.deepcopy(source)
        bank["bank_version"] = f"reference-{dataset}-20261025"
        bank["parent_bank"] = {"id": source["bank_version"], "canonical_sha256": digest(source),
                               "file_sha256": hashlib.sha256(previous.read_bytes()).hexdigest()}
        bank["execution_metadata_revision"] = "2026-10-25; title clusters retained; mixed-length clusters assigned one mixed stratification label; all original passages/questions/answers/offsets unchanged; initial POST rejected before any inference."
        bank["note"] += " 本运行版只修正标题簇跨长度分层的元数据冲突，原始篇章长度另存；未改原题原文答案。"
        clusters = defaultdict(set)
        for article in bank["articles"]:
            clusters[article["source_cluster_id"]].add(article["length_bin"])
        mixed = 0
        for article, old in zip(bank["articles"], source["articles"]):
            article["original_passage_length_bin"] = old["length_bin"]
            if len(clusters[article["source_cluster_id"]]) > 1:
                article["length_bin"] = "mixed_within_title_cluster"
                mixed += 1
            assert article["questions"] == old["questions"] and article["paragraphs"] == old["paragraphs"]
        scorer.validate_bank(bank, allow_draft=True)
        # Exercise the exact platform creation/refresh statistics path, with no
        # inference and no fabricated responses or review identities.
        scorer.evaluate(bank, [], ["admission-only-no-model"], allow_draft=True, bootstrap_repetitions=0)
        target = ROOT / f"data/annotation/reference-{dataset}-20261025.json"
        encoded = json.dumps(bank, ensure_ascii=False, indent=2) + "\n"
        if target.exists() and target.read_text(encoding="utf-8") != encoded:
            raise ValueError("Versioned execution bank already differs")
        target.write_text(encoded, encoding="utf-8")
        summary[dataset] = {"bank_id": bank["bank_version"], "canonical_sha256": digest(bank),
            "file_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "mixed_length_contexts": mixed,
            "passages": len(bank["articles"]), "original_qa_and_contexts_unchanged": True,
            "statistical_admission_passed": True, "human_review_count": 0}
    path = ROOT / "output/reference-execution-validation-20261025.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
