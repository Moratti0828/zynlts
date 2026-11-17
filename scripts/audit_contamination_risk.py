#!/usr/bin/env python3
"""Read-only, reproducible triage of the five downloaded candidate pools.

Flags are risks to investigate, not membership-inference or contamination labels.
The accompanying dated report contains the independent web sample evidence.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_candidate_pool import audit_record, near_duplicates, raw_body

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-10-13"
MODEL_RELEASE_UPPER_BOUND = "2024-09-19"
AGENCY = {"cas": "CAS", "cas_health": "CAS", "mct": "MCT", "mct_local": "MCT", "nbs": "NBS", "mee": "MEE", "nasa": "NASA", "nih": "NIH", "loc": "LOC", "census": "Census", "govuk": "GOV.UK multiple departments", "usgs": "USGS", "usgs_release": "USGS"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    pool_records, paths, inputs, mismatches = [], [], [], []
    for manifest in sorted((ROOT / "data/candidates").glob("*/source-discovery.json")):
        source = json.loads(manifest.read_text(encoding="utf-8-sig"))
        inputs.append({"path": manifest.relative_to(ROOT).as_posix(), "sha256": digest(manifest), "captures": len(source["captures"])})
        for record in source["captures"]:
            path = manifest.parent / "snapshots" / (record["id"] + ".metadata.json")
            metadata = json.loads(path.read_text(encoding="utf-8-sig"))
            changed = [key for key in ("text", "sha256", "raw_sha256", "published_at", "first_published_at") if metadata.get(key) != record.get(key)]
            if changed:
                mismatches.append({"id": record["id"], "fields": changed})
            pool_records.append(metadata)
            paths.append(path)
    duplicate_pairs = near_duplicates(pool_records)
    duplicate_ids = {pair[key] for pair in duplicate_pairs for key in ("left_id", "right_id")}
    correction_records = []
    for path in sorted((ROOT / "data/candidates").glob("*/publication-date-processing-log.json")):
        for candidate_id, old, new in json.loads(path.read_text(encoding="utf-8-sig")):
            correction_records.append({"id": candidate_id, "old_date": old, "corrected_date": new, "changed": old != new, "log_path": path.relative_to(ROOT).as_posix()})
    changed_ids = {r["id"] for r in correction_records if r["changed"]}
    records = []
    for source, path in zip(pool_records, paths):
        technical = audit_record(source, path, AS_OF, 600, 300)
        flags = ["global_earliest_publication_not_proven", "actual_training_membership_unknown", "question_answer_novelty_not_yet_reviewed"]
        if source.get("first_published_at"):
            flags.append("publisher_self_reported_first_publication_only")
        else:
            flags.append("source_first_publication_not_explicit")
        prior_years = sorted({int(y) for y in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-2][0-9])(?!\d)", source["text"]) if int(y) <= 2024})
        if prior_years:
            flags.append("pre_2025_year_mentions_require_question_level_review")
        if source.get("source_attribution"):
            flags.append("attribution_present_original_publisher_requires_review")
        if source["id"] in duplicate_ids:
            flags.append("high_lexical_similarity_family_split_risk")
        if source["id"] in changed_ids:
            flags.append("publication_date_selector_correction_logged")
        raw = (ROOT / source["raw_path"]).read_bytes()
        doi_targets = sorted({d.rstrip(".,;:)") for d in re.findall(r"10\.\d{4,9}/[A-Za-z0-9._;()/:-]+", raw.decode("utf-8", errors="replace"))})
        body_citation_marker = bool(re.search(r"相关研究成果|论文链接|\bDOI\b|\barXiv\b|\bpublished in\b|\bnew study\b", source["text"], re.I))
        if doi_targets or body_citation_marker:
            flags.append("underlying_research_or_reference_may_predate_news")
        if source.get("genre_provisional") == "weekly_digest":
            flags.append("weekly_digest_may_repeat_prior_releases")
        if source.get("published_at", "") <= MODEL_RELEASE_UPPER_BOUND:
            flags.append("page_not_after_conservative_model_bound")
        result = {key: source.get(key) for key in ("id", "title", "language", "provider", "source_name", "source_url", "source_attribution", "published_at", "first_published_at", "date_evidence", "sha256", "raw_sha256", "raw_path", "text_path", "genre_provisional", "domain_provisional")}
        result.update({"agency_group": AGENCY.get(source["provider"], source["provider"]), "page_date_after_model_bound": source.get("published_at", "") > MODEL_RELEASE_UPPER_BOUND, "prior_year_mentions": prior_years, "doi_targets_in_raw_heuristic": doi_targets, "risk_flags": flags, "technical_integrity_pass": technical["technical_integrity_pass"], "technical_errors": technical["errors"], "technical_flags": technical["flags"], "date_value_present_in_source": technical.get("date_value_present_in_source"), "publisher_organisations": technical.get("publisher_organisations", []), "earliest_global_publication": None, "training_seen_status": "unknown", "web_audit_status": "not_individually_web_searched", "human_review_status": "not_human_reviewed"})
        records.append(result)
    demo_file = ROOT / "data/corpus.json"
    demo = json.loads(demo_file.read_text(encoding="utf-8-sig"))["articles"]
    demo_rows = []
    candidate_url_ids = defaultdict(list)
    for record in records:
        candidate_url_ids[record["source_url"].rstrip("/")].append(record["id"])
    for article in demo:
        dates = {key: article.get(key) for key in ("published_at", "source_page_published_at", "first_published_at", "promulgated_at") if article.get(key)}
        demo_rows.append({"id": article["id"], "title": article["title"], "source_url": article["source_url"], "dates": dates, "all_recorded_dates_after_model_bound": all(d > MODEL_RELEASE_UPPER_BOUND for d in dates.values()), "questions": len(article["questions"]), "reviewed_field_limit": "AI compiled/source checked; not independent human review", "global_earliest_publication": None, "training_seen_status": "unknown", "same_source_in_candidate_ids": candidate_url_ids[article["source_url"].rstrip("/")], "risk_flags": ["global_earliest_publication_not_proven", "question_answer_prior_knowledge_requires_review", "development_demo_already_exposed_must_not_enter_hidden_test"]})
    models = json.loads((ROOT / "docs/model-source-snapshots/sources.json").read_text(encoding="utf-8-sig"))
    web_path = ROOT / "docs/contamination-web-samples-20261013.json"
    web = json.loads(web_path.read_text(encoding="utf-8-sig")) if web_path.exists() else {"candidate_samples": [], "demo_samples": [], "references": []}
    sample_by_id = {sample["id"]: sample for sample in web["candidate_samples"]}
    for record in records:
        if record["id"] in sample_by_id:
            record["web_audit_status"] = "AI_assisted_limited_source_and_prior_version_search"
            record["web_audit_findings"] = sample_by_id[record["id"]]
    for record in demo_rows:
        record["question_risks"] = [{"id": question["id"], "prompt": question["prompt"], "training_seen_status": "unknown", "answer_prior_publication_review": "not_individually_searched"} for question in next(article["questions"] for article in demo if article["id"] == record["id"])]
        sample = next((sample for sample in web["demo_samples"] if sample["id"] == record["id"]), None)
        if sample:
            record["web_audit_findings"] = sample
            for question in record["question_risks"]:
                if question["id"] in sample.get("prior_answer_evidence_question_ids", []):
                    question["answer_prior_publication_review"] = "related_answer_rule_publicly_documented_before_model_bound_not_proof_of_training_membership"
    hashes = defaultdict(list)
    for record in records:
        hashes[record["sha256"]].append(record["id"])
    audit = {"audit_version": "contamination-risk-triage-v1", "as_of_client_date": AS_OF, "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "scope": "402 local candidate records and 8 demonstration articles; all-record automatic triage, separate explicitly limited web samples, no human review or MIA experiment", "conservative_reference_model_release_upper_bound": MODEL_RELEASE_UPPER_BOUND, "inputs": inputs + [{"path": "data/corpus.json", "sha256": digest(demo_file)}], "counts": {"candidate_articles": len(records), "languages": dict(Counter(r["language"] for r in records)), "technical_integrity_pass": sum(r["technical_integrity_pass"] for r in records), "technical_integrity_fail": sum(not r["technical_integrity_pass"] for r in records), "source_first_published_explicit": sum(bool(r["first_published_at"]) for r in records), "source_first_published_unknown": sum(not r["first_published_at"] for r in records), "page_dates_after_model_bound": sum(r["page_date_after_model_bound"] for r in records), "earliest_global_publication_proven": 0, "training_membership_proven": 0, "human_reviewed": 0, "demo_articles": len(demo), "demo_questions": sum(len(a["questions"]) for a in demo)}, "candidate_publication_window": {"min": min(r["published_at"] for r in records), "max": max(r["published_at"] for r in records)}, "by_publication_month": dict(sorted(Counter(r["published_at"][:7] for r in records).items())), "by_agency_group": dict(Counter(r["agency_group"] for r in records)), "by_provider": dict(Counter(r["provider"] for r in records)), "date_evidence_kinds": dict(Counter(r["date_evidence"]["kind"] for r in records)), "risk_flag_counts": dict(Counter(flag for r in records for flag in r["risk_flags"])), "technical_error_counts": dict(Counter(error for r in records for error in r["technical_errors"])), "manifest_metadata_mismatches": mismatches, "exact_duplicate_groups": [ids for ids in hashes.values() if len(ids) > 1], "near_duplicate_pairs": duplicate_pairs, "near_duplicate_criteria": "same-language five-unit lexical shingle Jaccard >=0.65 or shorter containment >=0.85; min/max length ratio >=0.40; lexical flags cannot establish semantic independence or contamination", "usgs_date_selector_corrections": correction_records, "model_provenance": models, "model_provenance_limit": "Manifest/blob SHA fixes served bytes. It does not cryptographically attest original tensor -> GGUF conversion or establish complete pretraining/post-training history. Latest model release later than the pool publication dates is ineligible for the temporally isolated lane.", "records": records, "demo_records": demo_rows}
    audit["web_audit"] = web
    audit["counts"]["candidate_web_sampled"] = len(sample_by_id)
    audit["counts"]["candidate_not_individually_web_sampled"] = len(records) - len(sample_by_id)
    audit["counts"]["candidate_web_sampled_by_agency"] = dict(Counter(AGENCY[sample["provider"]] for sample in web["candidate_samples"]))
    output = ROOT / "output/contamination-risk-audit-20261013.json"
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: audit[key] for key in ("counts", "candidate_publication_window", "by_publication_month", "by_agency_group", "risk_flag_counts", "technical_error_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
