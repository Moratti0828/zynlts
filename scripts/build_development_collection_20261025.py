"""A deduplicated collection view of two already versioned recent draft banks."""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
from backend.benchmark_v2 import validate_bank
from backend.experiment_v2 import digest

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    files = [ROOT / "data/annotation/dev-expanded-20261020.json", ROOT / "data/annotation/dev-recent-additions-20261024.json"]
    banks = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    articles = [article for bank in banks for article in bank["articles"]]
    for key in ("id", "source_cluster_id", "presented_text_sha256", "source_text_sha256"):
        values = [article[key] for article in articles]
        if len(set(values)) != len(values):
            raise ValueError("Duplicate recent article identity or text: " + key)
    assert len(articles) == 40
    bank = {"schema_version": "reading-bank-v2", "bank_version": "dev-collection40-20261025", "formal": False,
            "human_review_count": 0, "annotation_origin": "AI_source_read_development_collection",
            "note": "40篇近期开发文章、320题，中英各20篇160题，人审0。两份版本化开发题库的去重汇总视图，不计作新增40篇或额外320题；公开历史参考与合成诊断不包含在内。",
            "collection_view": True, "parent_banks": [{"id": value["bank_version"], "canonical_sha256": digest(value),
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path, value in zip(files, banks)],
            "articles": articles}
    validate_bank(bank, allow_draft=True)
    assert Counter(a["language"] for a in articles) == {"zh": 20, "en": 20}
    assert sum(len(a["questions"]) for a in articles) == 320
    output = ROOT / "data/annotation/dev-collection40-20261025.json"
    encoded = json.dumps(bank, ensure_ascii=False, indent=2) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != encoded:
        raise ValueError("Existing collection differs; use a new version rather than overwrite")
    output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"bank": output.name, "unique_recent_articles": 40, "questions": 320, "canonical_sha256": digest(bank), "human_review_count": 0}))


if __name__ == "__main__":
    main()
