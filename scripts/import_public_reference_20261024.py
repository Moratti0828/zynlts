"""Import fixed official public dev subsets as contamination-exposed references.

This module never calls a model or the platform. Original contexts, questions,
answers and offsets are preserved; evidence is only a mechanical span proxy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.benchmark_v2 import validate_bank
from backend.experiment_v2 import messages
from backend.token_budget import prepare_budget

SOURCE_DIR = ROOT / "data/reference/sources-20261024"
SELECTION_SEED = "reading-reference-20261024-v1"
TARGET_PASSAGES = 50
QUESTIONS_PER_PASSAGE = 3
UNVERIFIED_MODEL = {"provider": "ollama", "model": "reference-budget-probe", "token_budget_margin": 512}

SOURCES = [
    {"key": "squad2_data", "filename": "squad2-dev.original.json", "url": "https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer/240e165ab706d95bd4323653bb92421f446208cf/dataset/dev-v2.0.json", "sha256": "80a5225e94905956a6446d296ca1093975c4d3b3260f1d6c8f68bc2ab77182d8", "revision": "240e165ab706d95bd4323653bb92421f446208cf", "dataset_file_commit_date": "2018-07-02"},
    {"key": "cmrc2018_data", "filename": "cmrc2018-dev.squad-style.json", "url": "https://raw.githubusercontent.com/ymcui/cmrc2018/5c81039ef856de178b5198391b3cd40f4e5e8514/squad-style-data/cmrc2018_dev.json", "sha256": "e9ff74231f05c230c6fa88b84441ee334d97234cbb610991cd94b82db00c7f1f", "revision": "5c81039ef856de178b5198391b3cd40f4e5e8514", "dataset_file_commit_date": "2019-03-29"},
    {"key": "squad2_software_license", "filename": "squad2-repository-LICENSE.txt", "url": "https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer/eee5fdbf62f8613a7812b03419e6b29617b74fd1/LICENSE", "sha256": "9c92e90621a47dc8508ddd78f0ee41a7b6a8fd5d37fd00709ff1c6eb1a7d7019", "applies_to": "repository software; MIT is not substituted for dataset terms"},
    {"key": "squad2_readme", "filename": "squad2-repository-README.md", "url": "https://raw.githubusercontent.com/rajpurkar/SQuAD-explorer/eee5fdbf62f8613a7812b03419e6b29617b74fd1/README.md", "sha256": "b03f46bef006f50547b9dd2abe2e8095f9751fc45678ab0fcb750fa524f557cf"},
    {"key": "squad2_dataset_license_evidence", "filename": "squad2-official-site.html", "url": "https://rajpurkar.github.io/SQuAD-explorer/", "sha256": "989f7e43f27faa490ed9fc8fb440e6f0aa791c49131346a27b8361deb4a18baf", "snapshot_date": "2026-10-24", "applies_to": "official page explicitly labels dataset CC BY-SA 4.0; page itself is not an immutable URL"},
    {"key": "cmrc2018_dataset_license", "filename": "cmrc2018-LICENCE.txt", "url": "https://raw.githubusercontent.com/ymcui/cmrc2018/c0eb1b6ba219847457e6af3180da722bbeb656af/LICENCE", "sha256": "7abe19ec9bb73b36141b999b861d24ad855e808bafe0f81e84cce28556f6c297", "applies_to": "official repository CC BY-SA 4.0"},
    {"key": "cmrc2018_readme", "filename": "cmrc2018-README.md", "url": "https://raw.githubusercontent.com/ymcui/cmrc2018/c0eb1b6ba219847457e6af3180da722bbeb656af/README.md", "sha256": "07047da7471a21f70b4fbe6756450fff761bf59cf4ccb8c1d5994724c661a436"},
    {"key": "cmrc2018_readme_cn", "filename": "cmrc2018-README_CN.md", "url": "https://raw.githubusercontent.com/ymcui/cmrc2018/c0eb1b6ba219847457e6af3180da722bbeb656af/README_CN.md", "sha256": "421ca4845266722ea07d1f234f7aa5002a6f58a461ae7b4bbeb937a01d94427a"},
]

DATASETS = {
    "squad2": {"name": "SQuAD 2.0 dev", "language": "en", "source_key": "squad2_data", "require_unanswerable": True,
               "authors": "Pranav Rajpurkar, Robin Jia, Percy Liang; original Wikipedia contributors",
               "paper": "https://aclanthology.org/P18-2124/", "license_source_key": "squad2_dataset_license_evidence"},
    "cmrc2018": {"name": "CMRC 2018 dev (official SQuAD-style conversion)", "language": "zh", "source_key": "cmrc2018_data", "require_unanswerable": False,
                 "authors": "Yiming Cui et al.; HIT / iFLYTEK CMRC 2018 organizers; original Chinese Wikipedia contributors",
                 "paper": "https://aclanthology.org/D19-1600/", "license_source_key": "cmrc2018_dataset_license"},
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha(value: Any) -> str:
    return sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def rank_key(*parts: str) -> str:
    return sha_bytes((SELECTION_SEED + "\0" + "\0".join(parts)).encode())


def verify_spans(context: str, qa: dict) -> None:
    """Reject bad official offsets; do not silently search for or repair answers."""
    impossible = qa.get("is_impossible", False)
    if type(impossible) is not bool:
        raise ValueError("is_impossible must be a boolean when present")
    answers = qa.get("answers")
    if not isinstance(answers, list) or (not impossible and not answers) or (impossible and answers):
        raise ValueError("Official answerability and answer list disagree")
    if not isinstance(qa.get("id"), str) or not isinstance(qa.get("question"), str) or not qa["question"].strip():
        raise ValueError("Missing original ID/question")
    for answer in answers + qa.get("plausible_answers", []):
        if not isinstance(answer, dict) or type(answer.get("answer_start")) is not int:
            raise ValueError("Answer offset is not an integer")
        start, text = answer["answer_start"], answer.get("text")
        if not isinstance(text, str) or not text.strip() or start < 0 or context[start:start + len(text)] != text:
            raise ValueError("Official answer text does not match its exact offset")


def choose_questions(context: str, qas: list[dict], dataset: str) -> tuple[list[dict], list[dict]]:
    valid, rejected = [], []
    for qa in qas:
        try:
            verify_spans(context, qa)
        except (TypeError, ValueError) as exc:
            rejected.append({"external_question_id": qa.get("id"), "reason": str(exc)})
        else:
            valid.append(qa)
    valid.sort(key=lambda q: rank_key(dataset, q["id"]))
    answerable = [q for q in valid if not q.get("is_impossible", False)]
    impossible = [q for q in valid if q.get("is_impossible", False)]
    if DATASETS[dataset]["require_unanswerable"]:
        selected = answerable[:2] + impossible[:1] if len(answerable) >= 2 and impossible else []
    else:
        selected = answerable[:QUESTIONS_PER_PASSAGE] if len(answerable) >= QUESTIONS_PER_PASSAGE else []
    return selected, rejected


def convert_passage(dataset: str, title: str, paragraph: dict, topic_index: int, paragraph_index: int,
                    questions: list[dict], source: dict) -> dict:
    spec, context = DATASETS[dataset], paragraph["context"]
    text_hash = sha_bytes(context.encode("utf-8"))
    identity = f"ref-{dataset}-{text_hash[:20]}"
    paragraph_id = identity + ":p001"
    items = []
    for index, qa in enumerate(questions, 1):
        impossible = qa.get("is_impossible", False)
        item = {"id": f"q{index:02d}", "kind": "unanswerable" if impossible else "short",
                "dimension": "D6" if impossible else "D1", "prompt": qa["question"],
                "evidence_sets": [] if impossible else [[paragraph_id]],
                "annotation_origin": "external_public_benchmark", "human_review_count": 0,
                "answer_gold_origin": "unmodified_official_public_dev_annotations",
                "external_question_id": qa["id"], "external_answers": qa["answers"],
                "external_is_impossible": impossible,
                "external_plausible_answers": qa.get("plausible_answers", []),
                "evidence_annotation_origin": "not_applicable" if impossible else "span_derived_proxy/draft",
                "evidence_gold_status": "not_applicable" if impossible else "unreviewed_proxy",
                "mapping_note": "Original question/answers/context unchanged; qNN aliases and whole-context paragraph ID are local metadata. D1 denotes extractive reference task, not independently adjudicated reasoning difficulty."}
        if impossible:
            item["missing_information"] = "The original SQuAD 2.0 development annotation labels this question unanswerable for this complete original context; no new human adjudication was performed in this project."
        else:
            item["answers"] = list(dict.fromkeys(a["text"] for a in qa["answers"]))
        items.append(item)
    return {"id": identity, "title": f"{DATASETS[dataset]['name']} · {title} · passage {paragraph_index + 1}",
            "language": spec["language"], "source_cluster_id": f"{dataset}-title-{sha_bytes(title.encode())[:20]}",
            "source_url": source["url"], "published_at": source["dataset_file_commit_date"],
            "first_published_at": None, "date_evidence": {"kind": "official_dataset_file_git_commit", "revision": source["revision"],
                "value": source["dataset_file_commit_date"], "meaning": "Publication of this official dataset file version; not a claim about Wikipedia article first publication."},
            "source_date_not_article_date": True,
            "rights": {"license": "CC-BY-SA-4.0", "attribution": spec["authors"], "license_source_key": spec["license_source_key"],
                "changes": "Only local metadata, IDs, deduplicated answer-alias list and span-derived whole-context evidence proxy were added; original passage, question and answer strings were not rewritten.",
                "redistribution_note": "Retain attribution, official source/revision, license notice and ShareAlike terms for adapted data. Software-repository MIT terms do not replace dataset terms."},
            "source_text_sha256": text_hash, "source_raw_sha256": source["sha256"],
            "source_raw_path": (Path("data/reference/sources-20261024") / source["filename"]).as_posix(),
            "scope": "full", "scope_note": "Complete original benchmark context retained byte-for-byte after JSON Unicode decoding. This is a reference passage, not the complete upstream Wikipedia article.",
            "split": "reference", "domain": "encyclopedic_reference", "length_bin": "short" if len(context) < 800 else "medium",
            "annotation_state": "candidate", "annotation_origin": "external_public_benchmark", "human_review_count": 0,
            "training_contamination_risk": "high_or_unknown", "requires_temporal_isolation": False,
            "evidence_annotation_origin": "span_derived_proxy/draft", "evidence_gold_status": "unreviewed_proxy",
            "external_dataset": dataset, "external_source_title": title, "external_topic_index": topic_index,
            "external_paragraph_index": paragraph_index, "external_context_id": paragraph.get("id"),
            "presented_text_sha256": text_hash,
            "paragraphs": [{"id": paragraph_id, "text": context, "source_paragraph_index": paragraph_index + 1}],
            "questions": items}


def select_passages(dataset: str, data: dict, source: dict, count: int = TARGET_PASSAGES) -> tuple[list[dict], dict]:
    """Hash-ranked title-round-robin sample, independent of all model outputs."""
    by_title: dict[str, list[dict]] = defaultdict(list)
    context_seen: set[str] = set()
    excluded = Counter()
    rejected_questions = []
    all_questions, duplicates = 0, 0
    for topic_index, topic in enumerate(data["data"]):
        title = topic["title"]
        for paragraph_index, paragraph in enumerate(topic["paragraphs"]):
            context = paragraph["context"]
            context_hash = sha_bytes(context.encode("utf-8"))
            all_questions += len(paragraph["qas"])
            if context_hash in context_seen:
                duplicates += 1
                continue
            context_seen.add(context_hash)
            if not context.strip():
                excluded["empty_context"] += 1
                continue
            selected_qs, invalid = choose_questions(context, paragraph["qas"], dataset)
            rejected_questions.extend(invalid)
            if len(selected_qs) != QUESTIONS_PER_PASSAGE:
                excluded["insufficient_valid_questions_or_answerability_mix"] += 1
                continue
            article = convert_passage(dataset, title, paragraph, topic_index, paragraph_index, selected_qs, source)
            budgets = [prepare_budget(UNVERIFIED_MODEL, messages(article, q, "with_context"), 512, 8192, False)
                       for q in article["questions"]]
            if not all(b["allowed"] for b in budgets):
                excluded["full_context_exceeds_conservative_budget"] += 1
                continue
            article["mechanical_validation"] = {"original_offsets_match": True, "full_context_unchanged": True,
                "max_conservative_total_tokens": max(b["total_tokens"] for b in budgets),
                "budget_method": "draft_utf8_byte_upper_bound; not certified exact tokenizer accounting"}
            by_title[title].append(article)
    for title in by_title:
        by_title[title].sort(key=lambda a: rank_key(dataset, title, a["source_text_sha256"]))
    titles = sorted(by_title, key=lambda title: rank_key(dataset, title))
    result, round_index = [], 0
    while len(result) < count:
        additions = [by_title[title][round_index] for title in titles if len(by_title[title]) > round_index]
        if not additions:
            break
        result.extend(additions[:count - len(result)])
        round_index += 1
    stats = {"original_topic_records": len(data["data"]), "available_original_titles": len({a["title"] for a in data["data"]}), "available_unique_contexts": len(context_seen),
             "original_questions": all_questions, "duplicate_contexts_excluded": duplicates,
             "eligible_titles": len(by_title), "eligible_contexts": sum(map(len, by_title.values())),
             "excluded_context_counts": dict(excluded), "rejected_original_question_spans": rejected_questions,
             "selected_reference_passages": len(result), "selected_source_title_clusters": len({a["source_cluster_id"] for a in result}),
             "selected_questions": sum(len(a["questions"]) for a in result),
             "question_kinds": dict(Counter(q["kind"] for a in result for q in a["questions"])),
             "context_truncations": 0, "answer_offset_repairs": 0}
    return result, stats


def verify_roundtrip(bank: dict, original: dict) -> dict:
    """Audit exported metadata directly against fixed raw records, without sampling."""
    question_count, span_count = 0, 0
    for article in bank["articles"]:
        topic = original["data"][article["external_topic_index"]]
        paragraph = topic["paragraphs"][article["external_paragraph_index"]]
        context = paragraph["context"]
        if article["external_source_title"] != topic["title"] or article["paragraphs"][0]["text"] != context:
            raise ValueError("Exported source title/context differs from original")
        if article["presented_text_sha256"] != sha_bytes(context.encode("utf-8")):
            raise ValueError("Exported context hash differs from original")
        originals = {qa["id"]: qa for qa in paragraph["qas"]}
        for item in article["questions"]:
            qa = originals[item["external_question_id"]]
            verify_spans(context, qa)
            if (item["prompt"] != qa["question"] or item["external_answers"] != qa["answers"] or
                item["external_is_impossible"] != qa.get("is_impossible", False) or
                item["external_plausible_answers"] != qa.get("plausible_answers", [])):
                raise ValueError("Exported original question/answer/offset/label changed")
            if not qa.get("is_impossible", False):
                if item["answers"] != list(dict.fromkeys(a["text"] for a in qa["answers"])):
                    raise ValueError("Exported answer aliases differ from original")
                if item["evidence_gold_status"] != "unreviewed_proxy":
                    raise ValueError("Mechanical evidence proxy was promoted to gold")
            question_count += 1
            span_count += len(qa["answers"]) + len(qa.get("plausible_answers", []))
    return {"passages_checked": len(bank["articles"]), "questions_checked": question_count,
            "original_answer_and_plausible_spans_checked": span_count, "all_original_strings_and_offsets_preserved": True}


def load_sources(fetch: bool) -> dict[str, dict]:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    records = {}
    for spec in SOURCES:
        path = SOURCE_DIR / spec["filename"]
        if not path.exists():
            if not fetch:
                raise FileNotFoundError(f"Missing fixed source {path}; use --fetch explicitly to retrieve official bytes")
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "reading-bench-reference-import/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read()
            if sha_bytes(raw) != spec["sha256"]:
                raise ValueError("Downloaded source differs from fixed SHA: " + spec["key"])
            path.write_bytes(raw)
        if sha_bytes(path.read_bytes()) != spec["sha256"]:
            raise ValueError("Existing source differs from fixed SHA: " + spec["key"])
        records[spec["key"]] = {**spec, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size}
    site = (SOURCE_DIR / records["squad2_dataset_license_evidence"]["filename"]).read_text(encoding="utf-8")
    if "CC BY-SA 4.0" not in re.sub(r"<[^>]+>", "", site):
        raise ValueError("Official SQuAD dataset license statement was not preserved")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Fetch absent official frozen source files; never overwrite mismatched bytes")
    args = parser.parse_args()
    sources = load_sources(args.fetch)
    summary = {"schema": "public-reference-import-audit-v1", "as_of_client_date": "2026-10-24", "formal": False,
               "human_review_count": 0, "selection_seed": SELECTION_SEED, "sources": list(sources.values()), "datasets": {}}
    for dataset, spec in DATASETS.items():
        source = sources[spec["source_key"]]
        original = json.loads((ROOT / source["path"]).read_bytes())
        articles, stats = select_passages(dataset, original, source)
        if len(articles) != TARGET_PASSAGES:
            raise ValueError(f"{dataset}: only {len(articles)} eligible full contexts; refusing to silently lower the target")
        bank = {"schema_version": "reading-bank-v2", "bank_version": f"reference-{dataset}-20261024", "formal": False,
                "human_review_count": 0, "as_of_client_date": "2026-10-24", "split": "reference",
                "annotation_origin": "external_public_benchmark", "answer_gold_origin": "unmodified_official_public_dev_annotations",
                "training_contamination_risk": "high_or_unknown", "requires_temporal_isolation": False,
                "evidence_annotation_origin": "span_derived_proxy/draft", "evidence_gold_status": "unreviewed_proxy",
                "primary_reference_metrics": ["short_em", "short_token_f1", "correct_refusal_rate", "format_error_rate"],
                "evidence_metrics_interpretation": "Exploratory mechanical proxy only; excluded from claims about true support-chain quality.",
                "metric_protocol": "reading-bench project normalization and character/word F1, not official SQuAD/CMRC leaderboard scoring",
                "note": "公开历史参考子集，可能已被模型训练见过；不是近期无污染题库或正式隐藏测试。原题/原文/原答案保持，证据仅span派生代理；本项目人工复核0。",
                "reference_dataset": {"id": dataset, "name": spec["name"], "paper": spec["paper"], "source": source,
                    "license": "CC-BY-SA-4.0", "attribution": spec["authors"], "license_evidence": sources[spec["license_source_key"]]},
                "sampling": {"seed": SELECTION_SEED, "method": "SHA256-ranked source-title round robin, then SHA-ranked full contexts; no model outputs inspected",
                    "questions_per_passage": QUESTIONS_PER_PASSAGE,
                    "question_mix": "two original answerable plus one original impossible" if spec["require_unanswerable"] else "three original answerable",
                    "source_cluster_policy": "Same original title shares one cluster; contexts are not counted as independent upstream Wikipedia articles."},
                "articles": articles}
        validate_bank(bank, allow_draft=True)
        roundtrip = verify_roundtrip(bank, original)
        # Preserve the initial import as an offline lineage artifact. The
        # 20261025 execution version fixes title-cluster stratification only.
        path = ROOT / f"data/reference/initial-import-banks-20261024/reference-{dataset}-20261024.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(bank, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and canonical_sha(json.loads(path.read_bytes())) != canonical_sha(bank):
            raise ValueError("Refusing to replace a dated bank with changed data; create a new version ID")
        if not path.exists():
            path.write_bytes(encoded)
        summary["datasets"][dataset] = {**stats, "schema_valid": True, "path": path.relative_to(ROOT).as_posix(),
                                       "roundtrip_validation": roundtrip,
                                       "file_sha256": sha_bytes(path.read_bytes()), "canonical_bank_sha256": canonical_sha(bank)}
    manifest_path = SOURCE_DIR / "manifest.json"
    manifest_path.write_text(json.dumps({"captured_client_date": "2026-10-24", "sources": list(sources.values()),
        "license_note": "Dataset terms CC BY-SA 4.0; SQuAD repository software LICENSE MIT is preserved separately. Preserve attribution/ShareAlike for adapted data."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = ROOT / "output/public-reference-validation-20261024.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {f: v[f] for f in ("selected_reference_passages", "selected_source_title_clusters", "selected_questions", "question_kinds", "file_sha256")} for k, v in summary["datasets"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
