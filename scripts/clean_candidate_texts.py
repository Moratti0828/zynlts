#!/usr/bin/env python3
"""Version derived candidate prose to remove captured page UI, preserving raw.

The complete previous metadata/TXT is archived in processing-history. Original
HTTP snapshots and every historical benchmark record remain unchanged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import discover_recent_sources as collector

ROOT = collector.ROOT
RIGHTS_REFERENCE = {
    "govuk": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    "nasa": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
    "nih": "https://www.nih.gov/about-nih/site-guide",
    "loc": "https://www.loc.gov/legal/",
    "census": "https://www.census.gov/about/policies/copyright.html",
    "usgs": "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
    "usgs_release": "https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean(pool: Path) -> dict:
    manifest_path = pool / "source-discovery.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    captures = []
    reports = []
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for item in manifest["captures"]:
        previous = json.loads(json.dumps(item))
        provider = item["provider"]
        para = item["paragraphs"]
        selector = item["extraction_selector"]
        provenance_changed = False
        if provider == "nih":
            document = collector.soup((ROOT / item["raw_path"]).read_bytes())
            body = document.select_one("article[data-history-node-id]")
            if body:
                para = collector.paragraphs(body)
                selector = "article[data-history-node-id]"
            # Bibliographic references preceding the agency-contact panel remain.
            tail = next((i for i, text in enumerate(para) if text == "Institute/Center"), None)
            if tail is not None:
                para = para[:tail]
        elif provider == "nasa":
            api_item = json.loads((ROOT / item["raw_path"]).read_text(encoding="utf-8"))
            body = collector.soup(api_item["content"]["rendered"].encode("utf-8"))
            para = collector.paragraphs(body)
            for page in manifest["discovery_pages"]:
                if page.get("url") == item["request_url"] and page.get("raw_path"):
                    original = json.loads((ROOT / page["raw_path"]).read_bytes())
                    matching = next((source_item for source_item in original if source_item.get("id") == api_item.get("id")), None)
                    if matching != api_item:
                        raise ValueError("NASA API item differs from unmodified original HTTP response")
                    item.update({"raw_capture_kind": "parsed_official_api_item", "raw_capture_note": "raw_path is a parsed official API item serialized as JSON; raw_sha256 hashes this item snapshot, not original HTTP bytes. discovery_raw_path preserves the complete unmodified HTTP JSON response.",
                                 "discovery_raw_path": page["raw_path"], "discovery_raw_sha256": page["raw_sha256"],
                                 "downloaded_at": page["downloaded_at"], "official_api_item_id": api_item["id"]})
                    provenance_changed = True
                    break
        removed = []
        kept = []
        for text in para:
            reason = None
            if text == item["title"]:
                reason = "duplicate article heading"
            elif re.match(r"^(Subscribe\b|Connect with Us$|Get an alert directly in your inbox|Contact our Public Information Office|NIH Office of Communications$|\d+\s+min\s+read$|>>>更多内容)", text, re.I):
                reason = "page subscription/contact/read-time/navigation UI"
            elif provider.startswith("cas") and re.match(r"^图\s*\d+", text) and len(text) < 220:
                reason = "standalone numbered illustration caption; prose-only candidate"
            if reason:
                removed.append({"text": text, "reason": reason})
            else:
                kept.append(text)
        new_text = "\n\n".join(kept)
        changed = sha(new_text) != previous["sha256"] or selector != previous["extraction_selector"]
        if changed or provenance_changed:
            history = pool / "processing-history"
            history.mkdir(exist_ok=True)
            old_metadata = history / (item["id"] + ".v1.metadata.json")
            if old_metadata.exists():
                raise ValueError(f"Already processed {item['id']}; cannot overwrite the processing history")
            old_metadata.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            shutil.copyfile(ROOT / item["text_path"], history / (item["id"] + ".v1.txt"))
            item.update({"text": new_text, "paragraphs": kept, "sha256": sha(new_text), "body_bytes": len(new_text.encode("utf-8")),
                         "word_count": len(re.findall(r"\b[\w'-]+\b", new_text)) if item["language"] == "en" else None,
                         "han_count": len(re.findall(r"[\u4e00-\u9fff]", new_text)), "extraction_selector": selector,
                         "derived_text_processing_log": {"version": "candidate-prose-cleaning-v1", "processed_at": timestamp,
                             "previous_text_sha256": previous["sha256"], "previous_selector": previous["extraction_selector"],
                             "history_metadata_path": str(old_metadata.relative_to(ROOT)).replace("\\", "/"),
                             "removed_paragraphs": removed, "original_paragraph_count": len(previous["paragraphs"]), "result_paragraph_count": len(kept),
                             "policy": "Remove only page UI/recommendation containers, repeated title and standalone numbered CAS image captions; preserve original wording and document paragraphs. Raw source bytes unchanged."}})
            (ROOT / item["text_path"]).write_text(new_text + "\n", encoding="utf-8", newline="\n")
        if provider == "mee" and "一周要闻" in item["title"]:
            item["genre_provisional"] = "weekly_digest"
            item["selection_cautions"] = ["Multi-story weekly digest; should not fill a coherent single-article quota."]
        item.setdefault("raw_capture_kind", "http_response_bytes")
        item["rights_reference_url"] = RIGHTS_REFERENCE.get(provider)
        item["rights_review_status"] = "pending_article_author_and_third_party_rights_review"
        item["reviewed"] = False
        item["human_reviewed"] = False
        item["status"] = "candidate"
        metadata_path = pool / "snapshots" / (item["id"] + ".metadata.json")
        metadata_path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        captures.append(item)
        reports.append({"id": item["id"], "text_changed": changed, "provenance_changed": provenance_changed,
                        "previous_sha256": previous["sha256"], "sha256": item["sha256"], "removed_paragraphs": len(removed)})
    manifest["captures"] = captures
    manifest["processed_at"] = timestamp
    manifest["processing_notice"] = "Derived body text/provenance corrected with immutable previous versions in processing-history; all original HTTP snapshots unchanged. No human review or gold answers created."
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    result = {"pool": str(pool.relative_to(ROOT)).replace("\\", "/"), "processed_at": timestamp,
              "counts": dict(Counter("changed" if item["text_changed"] else "unchanged" for item in reports)), "articles": reports}
    (pool / "derived-text-processing-log.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pools", nargs="+", type=Path)
    args = parser.parse_args()
    for pool in args.pools:
        pool = pool.resolve()
        if not pool.is_relative_to(ROOT / "data/candidates"):
            parser.error("Only candidate pools under data/candidates may be processed")
        result = clean(pool)
        print(json.dumps({"pool": result["pool"], "counts": result["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
