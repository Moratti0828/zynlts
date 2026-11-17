#!/usr/bin/env python3
"""Read-only audit of downloaded source candidates; does not create gold labels.

Hashes use exact bytes. The Windows .txt writer may translate LF to CRLF and
add one terminal newline; these forms are checked without stripping body text.
Near duplicates and UI strings are triage flags, not automatic semantic verdicts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r"[\u4e00-\u9fff]")
WORDS = re.compile(r"\b[\w'-]+\b")
UI = re.compile(r"^(?:share(?: this)?(?: article| story| page)?|related (?:content|articles|stories)|subscribe(?: to)?|print(?: this)?|back to top|follow us|sign up|related topics|contact us|latest news|相关新闻|相关链接|分享到|打印本页|关闭窗口|返回顶部|上一篇|下一篇)(?:\b|[：:]|$)", re.I)
MORE_LINK = re.compile(r"^(?:[>》]{2,}\s*)?(?:更多内容[，,]?\s*点击阅读|\d+\s+min(?:ute)?s?\s+read)$", re.I)
CENSUS_UI = re.compile(r"^(?:Get an alert directly in your inbox|Contact our Public Information Office|Subscribe to receive|Stay connected with)", re.I)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", html.unescape(text)).casefold()


def percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    return values[round((len(values) - 1) * fraction)]


def date_value(value) -> str | None:
    if not isinstance(value, str):
        return None
    m = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", value)
    if m:
        try:
            return dt.date(*(int(v) for v in m.groups())).isoformat()
        except ValueError:
            return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%A, %B %d, %Y"):
        try:
            return dt.datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def contained_file(value) -> Path:
    if not isinstance(value, str):
        raise ValueError("Missing file path")
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT / "data/candidates"):
        raise ValueError("Snapshot path outside candidate directory")
    return path


def json_values(value, field):
    if isinstance(value, dict):
        if field in value:
            yield value[field]
        for child in value.values():
            yield from json_values(child, field)
    elif isinstance(value, list):
        for child in value:
            yield from json_values(child, field)


def raw_body(raw: bytes, record: dict):
    api = None
    provider = record.get("provider")
    if record.get("content_type", "").startswith("application/json") or str(record.get("raw_path", "")).endswith(".api.json"):
        api = json.loads(raw)
        if provider == "govuk":
            content = api.get("details", {}).get("body", "")
        elif provider == "nasa":
            content = api.get("content", {}).get("rendered", "")
        else:
            content = json.dumps(api, ensure_ascii=False)
        soup = BeautifulSoup(content, "html.parser")
        return soup, soup, api
    soup = BeautifulSoup(raw, "html.parser")
    selector = record.get("extraction_selector")
    if selector and selector.startswith("all ") and selector.endswith(" in DOM order"):
        found = soup.select(selector[4:-13])
        combined = BeautifulSoup("\n".join(str(element) for element in found), "html.parser")
        return soup, combined, api
    found = soup.select(selector) if selector else []
    return soup, max(found, key=lambda element: len(element.get_text())) if found else soup, api


def audit_record(record: dict, metadata_path: Path, as_of: str, min_han: int, min_words: int) -> dict:
    errors, flags = [], []
    text = record.get("text", "")
    paragraphs = record.get("paragraphs", [])
    result = {"id": record.get("id"), "metadata_path": str(metadata_path.relative_to(ROOT)).replace("\\", "/"),
              "title": record.get("title"), "language": record.get("language"), "provider": record.get("provider"),
              "source_name": record.get("source_name"), "source_url": record.get("source_url"),
              "published_at": record.get("published_at"), "first_published_at": record.get("first_published_at"),
              "date_evidence_kind": record.get("date_evidence", {}).get("kind"),
              "domain_provisional": record.get("domain_provisional"), "genre_provisional": record.get("genre_provisional"),
              "recency_tier": record.get("recency_tier"), "sha256": record.get("sha256")}
    for key in ("id", "title", "provider", "source_name", "source_url", "language", "published_at", "date_evidence", "rights", "scope", "extraction_selector", "sha256", "raw_sha256", "raw_path", "text_path"):
        if not record.get(key):
            errors.append("missing_" + key)
    if "first_published_at" not in record:
        errors.append("missing_first_published_field")
    if record.get("reviewed") is not False:
        errors.append("candidate_reviewed_must_be_false")
    if record.get("questions"):
        flags.append("unexpected_questions_in_source_candidate")
    if record.get("language") not in {"zh", "en"}:
        errors.append("invalid_language_label")
    url = urlsplit(record.get("source_url", ""))
    if url.scheme not in {"http", "https"} or not url.netloc:
        errors.append("invalid_source_url")
    published = date_value(record.get("published_at"))
    if published is None:
        errors.append("invalid_publication_date")
    elif published > as_of:
        errors.append("future_publication_date")
    if record.get("first_published_at") is None:
        flags.append("earliest_publication_unverified")
    elif date_value(record.get("first_published_at")) is None:
        errors.append("invalid_first_publication_date")
    if not isinstance(text, str) or not text:
        errors.append("empty_body")
        text = ""
    body = text.encode("utf-8")
    result["body_bytes"] = len(body)
    result["han_count"] = len(HAN.findall(text))
    result["word_count"] = len(WORDS.findall(text)) if record.get("language") == "en" else None
    result["paragraph_count"] = len(paragraphs)
    if sha(body) != record.get("sha256"):
        errors.append("metadata_text_sha_mismatch")
    if "\n\n".join(paragraphs) != text:
        errors.append("paragraph_text_mismatch")
    try:
        txt = contained_file(record.get("text_path")).read_bytes()
        windows_body = body.replace(b"\n", b"\r\n")
        if txt not in {body, body + b"\n", body + b"\r\n", windows_body, windows_body + b"\r\n"}:
            errors.append("txt_does_not_match_metadata_text")
        result["txt_sha256_with_saved_newline"] = sha(txt)
        result["txt_line_ending"] = "CRLF" if b"\r\n" in txt else "LF"
    except (OSError, ValueError) as exc:
        errors.append("text_file_error:" + str(exc))
    result["meets_recommended_length"] = (result["han_count"] >= min_han if record.get("language") == "zh" else (result["word_count"] or 0) >= min_words)
    if not result["meets_recommended_length"]:
        flags.append("below_recommended_length")
    if len(body) > 6000:
        flags.append("exceeds_current_6000_byte_passage_budget")
    visible_chars = len(re.sub(r"\s", "", text))
    if record.get("language") == "zh" and result["han_count"] / max(1, visible_chars) < .20:
        flags.append("language_label_requires_review")
    if record.get("language") == "en" and result["han_count"] / max(1, visible_chars) > .15:
        flags.append("language_label_requires_review")
    ui = [paragraph for paragraph in paragraphs if UI.search(paragraph.strip())]
    ui.extend(paragraph for paragraph in paragraphs if MORE_LINK.search(paragraph.strip()) and paragraph not in ui)
    ui.extend(paragraph for paragraph in paragraphs if CENSUS_UI.search(paragraph.strip()) and paragraph not in ui)
    if ui:
        flags.append("possible_navigation_or_subscription_text")
    repeated_title = [i for i, paragraph in enumerate(paragraphs) if compact(paragraph) == compact(str(record.get("title", "")))]
    if repeated_title:
        flags.append("standalone_repeated_title_or_caption")
    result["ui_string_examples"] = ui[:3]
    result["standalone_title_paragraphs"] = repeated_title
    try:
        raw = contained_file(record.get("raw_path")).read_bytes()
        if sha(raw) != record.get("raw_sha256"):
            errors.append("raw_sha_mismatch")
        soup, extracted, api = raw_body(raw, record)
        raw_text = compact(extracted.get_text(" ", strip=True))
        unsupported = []
        for index, paragraph in enumerate(paragraphs):
            # Table rows contain added separators, but each cell must exist.
            parts = paragraph.split(" | ") if " | " in paragraph else [paragraph]
            if any(compact(part) and compact(part) not in raw_text for part in parts):
                unsupported.append(index)
        result["paragraphs_not_found_in_source_body"] = unsupported
        if unsupported:
            errors.append("paragraph_not_traceable_in_source_body")
        evidence = record.get("date_evidence", {})
        value = evidence.get("value")
        evidence_found = False
        if api is not None and evidence.get("field"):
            evidence_found = value in list(json_values(api, evidence["field"]))
        elif evidence.get("kind") == "publication_meta":
            for element in soup.find_all("meta"):
                keys = {str(element.get(attribute, "")).casefold() for attribute in ("name", "property")}
                if str(evidence.get("field", "")).casefold() in keys and element.get("content") == value:
                    evidence_found = True
        elif evidence.get("kind") == "json_ld":
            for element in soup.select('script[type="application/ld+json"]'):
                try:
                    if value in list(json_values(json.loads(element.string or element.get_text()), evidence.get("field"))):
                        evidence_found = True
                except (ValueError, TypeError):
                    pass
        else:
            evidence_found = str(value or "") in soup.get_text(" ", strip=True) or str(value or "") in raw.decode("utf-8", errors="replace")
        result["date_value_present_in_source"] = evidence_found
        if not evidence_found:
            errors.append("date_evidence_not_traceable_in_raw")
        if date_value(value) != published:
            errors.append("date_evidence_value_mismatch")
        if record.get("provider") == "nasa":
            # An API item is useful provenance, but is not an exact HTTP response.
            result["raw_representation"] = "serialized_api_item"
            result["original_http_api_item_match"] = False
            if record.get("raw_capture_kind") != "parsed_official_api_item":
                flags.append("nasa_api_item_capture_kind_missing")
            if not record.get("discovery_raw_path") or not record.get("discovery_raw_sha256"):
                flags.append("nasa_api_item_serialization_requires_original_response_link")
            else:
                original = contained_file(record["discovery_raw_path"]).read_bytes()
                result["discovery_raw_path"] = record["discovery_raw_path"]
                result["discovery_raw_sha256_verified"] = sha(original) == record["discovery_raw_sha256"]
                if not result["discovery_raw_sha256_verified"]:
                    errors.append("nasa_original_http_sha_mismatch")
                values = json.loads(original)
                items = [item for item in values if isinstance(item, dict) and item.get("id") == api.get("id")]
                result["original_http_api_item_match"] = len(items) == 1 and items[0] == api
                if not result["original_http_api_item_match"]:
                    errors.append("nasa_item_does_not_match_original_http_json")
        else:
            result["raw_representation"] = "http_response_bytes"
        if api is not None and record.get("provider") == "govuk":
            organisations = api.get("links", {}).get("organisations", [])
            result["publisher_organisations"] = [x.get("title") for x in organisations if isinstance(x, dict) and x.get("title")]
        result["source_body_excerpt"] = extracted.get_text(" ", strip=True)[:180]
    except (OSError, ValueError, TypeError) as exc:
        errors.append("raw_read_or_parse_error:" + str(exc))
    result["head_excerpt"] = text[:220]
    result["tail_excerpt"] = text[-220:]
    result["errors"] = errors
    result["flags"] = flags
    result["technical_integrity_pass"] = not errors
    return result


def shingles(text: str, language: str) -> set[str]:
    units = WORDS.findall(text.casefold()) if language == "en" else list(compact(text))
    return {" ".join(units[i:i + 5]) for i in range(max(0, len(units) - 4))}


def near_duplicates(records: list[dict]) -> list[dict]:
    signatures = {r["id"]: shingles(r["text"], r["language"]) for r in records}
    matches = []
    for left, right in itertools.combinations(records, 2):
        if left["language"] != right["language"] or left.get("sha256") == right.get("sha256"):
            continue
        a, b = signatures[left["id"]], signatures[right["id"]]
        if not a or not b or min(len(a), len(b)) / max(len(a), len(b)) < .40:
            continue
        overlap = len(a & b)
        jaccard = overlap / max(1, len(a | b))
        containment = overlap / min(len(a), len(b))
        if jaccard >= .65 or containment >= .85:
            matches.append({"left_id": left["id"], "right_id": right["id"], "left_title": left.get("title"), "right_title": right.get("title"), "five_shingle_jaccard": round(jaccard, 4), "shorter_containment": round(containment, 4), "status": "possible_template_family_or_duplicate_requires_review"})
    return sorted(matches, key=lambda item: item["five_shingle_jaccard"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", nargs="+", type=Path, default=[ROOT / "data/candidates/20261011-source-discovery"])
    parser.add_argument("--as-of", default="2026-10-11")
    parser.add_argument("--min-han", type=int, default=600)
    parser.add_argument("--min-words", type=int, default=300)
    parser.add_argument("--json-output", type=Path, default=ROOT / "output/candidate-pool-audit.json")
    parser.add_argument("--report-output", type=Path, default=ROOT / "docs/candidate-pool-audit.md")
    args = parser.parse_args()
    dt.date.fromisoformat(args.as_of)
    records, paths, pools, manifest_mismatches = [], [], [], []
    for pool in args.pool:
        pool = pool.resolve()
        manifest = pool / "source-discovery.json"
        ids = None
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            ids = {r["id"] for r in data.get("captures", [])}
            manifest_records = {r["id"]: r for r in data.get("captures", [])}
        snapshots = sorted((pool / "snapshots").glob("*.metadata.json"))
        pools.append({"path": str(pool.relative_to(ROOT)).replace("\\", "/"), "manifest_complete": manifest.exists(), "snapshot_metadata_files": len(snapshots), "manifest_captures": len(ids) if ids is not None else None})
        for path in snapshots:
            record = json.loads(path.read_text(encoding="utf-8"))
            if ids is None or record.get("id") in ids:
                records.append(record)
                paths.append(path)
                if ids is not None:
                    mismatch_fields = [key for key in ("sha256", "raw_sha256", "text", "published_at", "first_published_at", "reviewed") if record.get(key) != manifest_records[record["id"]].get(key)]
                    if mismatch_fields:
                        manifest_mismatches.append({"id": record["id"], "pool": str(pool.relative_to(ROOT)).replace("\\", "/"), "fields": mismatch_fields})
    audited = [audit_record(r, path, args.as_of, args.min_han, args.min_words) for r, path in zip(records, paths)]
    hash_groups, url_groups = defaultdict(list), defaultdict(list)
    for record in records:
        hash_groups[record.get("sha256")].append(record["id"])
        url_groups[record.get("source_url")].append(record["id"])
    exact = [ids for ids in hash_groups.values() if len(ids) > 1]
    duplicate_urls = [ids for ids in url_groups.values() if len(ids) > 1]
    by_language = {}
    for language in ("zh", "en"):
        rows = [r for r in audited if r["language"] == language]
        counts = [r["han_count"] if language == "zh" else r["word_count"] for r in rows]
        by_language[language] = {"downloaded_candidates": len(rows), "distinct_text_bodies": len({r["sha256"] for r in rows}), "technical_integrity_pass": sum(r["technical_integrity_pass"] for r in rows), "recommended_length_and_integrity_pass": sum(r["technical_integrity_pass"] and r["meets_recommended_length"] for r in rows), "length_budget_no_ui_screen_pass": sum(r["technical_integrity_pass"] and r["meets_recommended_length"] and r["body_bytes"] <= 6000 and not r["ui_string_examples"] for r in rows), "within_existing_model_passage_budget": sum(r["body_bytes"] <= 6000 for r in rows), "length_unit": "Han characters" if language == "zh" else "regex words", "minimum": min(counts) if counts else None, "median": percentile(counts, .5), "p10": percentile(counts, .1), "p90": percentile(counts, .9), "maximum": max(counts) if counts else None}
    samples = []
    for provider in sorted({r["provider"] for r in audited}):
        ordered = sorted([r for r in audited if r["provider"] == provider], key=lambda row: row["body_bytes"])
        for row in {ordered[0]["id"]: ordered[0], ordered[len(ordered) // 2]["id"]: ordered[len(ordered) // 2]}.values():
            samples.append({key: row.get(key) for key in ("id", "provider", "title", "source_url", "body_bytes", "date_value_present_in_source", "paragraphs_not_found_in_source_body", "head_excerpt", "tail_excerpt", "flags", "errors")})
    audit = {"audit_version": "candidate-pool-audit-v1", "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "as_of": args.as_of,
             "status": "complete_download_snapshot_audit" if all(p["manifest_complete"] for p in pools) else "in_progress_snapshot_audit",
             "scope": "Read-only technical checks plus AI-assisted triage; no human adjudication, gold questions, copyright approval or contamination proof.", "pools": pools,
             "criteria": {"recommended_zh_min_han": args.min_han, "recommended_en_min_words": args.min_words, "existing_passage_budget_bytes": 6000, "near_duplicate_rule": "same-language five-shingle Jaccard >= 0.65 or shorter containment >= 0.85; semantic review required"},
             "counts": {"snapshot_records_in_manifest": len(records), "distinct_urls": len(url_groups), "exact_distinct_body_hashes": len(hash_groups), "technical_integrity_pass": sum(r["technical_integrity_pass"] for r in audited), "technical_integrity_reject": sum(not r["technical_integrity_pass"] for r in audited), "human_reviewed_articles": 0, "gold_questions": 0, "formal_frozen_articles": 0},
             "language": by_language, "provider": dict(Counter(r["provider"] for r in audited)), "domain_provisional": dict(Counter(r["domain_provisional"] for r in audited)), "genre_provisional": dict(Counter(r["genre_provisional"] for r in audited)), "recency_tier": dict(Counter(r["recency_tier"] for r in audited)), "date_evidence_kind": dict(Counter(r["date_evidence_kind"] for r in audited)),
             "first_publication_known": sum(r["first_published_at"] is not None for r in audited), "first_publication_unknown": sum(r["first_published_at"] is None for r in audited),
             "earliest_global_publication_verified": 0,
             "error_counts": dict(Counter(error for r in audited for error in r["errors"])), "flag_counts": dict(Counter(flag for r in audited for flag in r["flags"])),
             "manifest_metadata_mismatches": manifest_mismatches,
             "exact_duplicate_groups": exact, "duplicate_url_groups": duplicate_urls, "near_duplicate_pairs": near_duplicates(records), "institution_samples": samples, "records": audited}
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = audit["counts"]
    lines = ["# 新下载候选文章池独立审计", "", f"审计日期：{args.as_of}。状态：`{audit['status']}`。审计器只读取候选文件，不修改原始快照、采集器、现有 8 篇演示题库或评分器。", "", "本报告是技术检查与 AI 辅助审查；**人工审定文章、已审金标题目和正式冻结文章均为 0**。正文可追溯不等于语义质量、授权、最早首发或完全无训练污染已经证明。", "", "## 核实后的数量", "", f"manifest 中候选记录 {counts['snapshot_records_in_manifest']}；独立 URL {counts['distinct_urls']}；不同正文 SHA-256 {counts['exact_distinct_body_hashes']}。技术完整性通过 {counts['technical_integrity_pass']}，拒收/待修复 {counts['technical_integrity_reject']}；manifest/metadata 关键字段不一致 {len(manifest_mismatches)} 条。", "", "| 语言 | 下载候选 | 技术完整性通过 | 同时达建议长度 | 当前 6000 字节模型正文预算内 | 长度中位数 |", "|---|---:|---:|---:|---:|---:|"]
    for lang, value in by_language.items():
        lines.append(f"| {lang} | {value['downloaded_candidates']} | {value['technical_integrity_pass']} | {value['recommended_length_and_integrity_pass']} | {value['within_existing_model_passage_budget']} | {value['median']} |")
    lines.extend(["", f"建议长度是中文至少 {args.min_han} 个汉字、英文至少 {args.min_words} 个正则分词，不是采集硬门槛或自动入选标准；短而完整的文章仍可人工例外，长文章也不能擅自截断。正文预算仅指当前 6000 UTF-8 字节约束，提示词和输出还占额外预算。", "", "## 真实性、日期与完整性", "", "逐篇核对 metadata.text 的 SHA-256、txt 保存字节、原始快照 SHA-256、段落拼接一致性、来源地址、语言标签、日期字段和未审状态，并核对每段文字能在机构正文选择器/API body 中找到。txt 的 Windows CRLF 转换及单个末尾换行与正文哈希分开报告，不删除正文空白。NASA API item 重序列化文件不是整个 HTTP 响应，须连到 discovery 原始响应后才构成完整取证链。", "", f"来源明确自报 first_published_at 的 {audit['first_publication_known']} 篇，未自报的 {audit['first_publication_unknown']} 篇；全球最早公开时间独立核定为 0 篇。publication_meta、页面 header 或 WordPress date 只能支持该来源的发布日期；不自动证明没有更早论文、转载或早期报道。URL 日期、Last-Modified、updated 字段没有被当作首发证据。", "", "## 重复与正文污染风险", "", f"准确重复正文组 {len(exact)}；重复 URL 组 {len(duplicate_urls)}；高相似文本对 {len(audit['near_duplicate_pairs'])}。五单位 shingle 筛查不能代替语义独立性审查：同一统计系列、同一事件的报道以及共享调查说明应归入同组，划分开发/测试时不得跨组。", ""])
    for label, number in sorted(audit["flag_counts"].items()):
        lines.append(f"- `{label}`：{number} 篇。")
    if audit["error_counts"]:
        lines.extend(["", "技术拒收原因："])
        for label, number in sorted(audit["error_counts"].items()):
            lines.append(f"- `{label}`：{number}。")
    lines.extend(["", "## 来源、领域与体裁", "", "来源计数按采集 provider，而不是已经人工核定的作者或独立机构。GOV.UK 的原始 Content API 中 organisations 在 JSON 审计记录中另列；科学院下属研究所也不能自动当成完全独立文章来源。领域与体裁目前仅是 provisional 标签。", "", "| 来源 | 候选数 |", "|---|---:|"])
    for label, number in sorted(audit["provider"].items()):
        lines.append(f"| {label} | {number} |")
    lines.extend(["", "领域：`" + json.dumps(audit["domain_provisional"], ensure_ascii=False) + "`。", "", "体裁：`" + json.dumps(audit["genre_provisional"], ensure_ascii=False) + "`。", "", "## 每机构正文抽样", "", "下列每机构至少两篇（若总共不足两篇则全看）按最短与中位长度抽样，结合 raw 正文与头尾文本作独立 AI 辅助核对。全部篇目已执行技术追溯，但本抽样不属于人工审稿或对各句事实的核验。", ""])
    for sample in samples:
        lines.extend([f"- `{sample['id']}` [{sample['title']}]({sample['source_url']})：{sample['body_bytes']} 字节；日期原值在 raw 中：{sample['date_value_present_in_source']}；未追溯段落：{sample['paragraphs_not_found_in_source_body']}；标记：`{', '.join(sample['flags']) or '无'}`。"])
    lines.extend(["", "## 入选前仍需完成", "", "1. 清理导航、相关链接、标题重复与无图可读的图注，保存清理前后版本及可追溯段落映射。", "2. 核查转载、论文与事件的最早公开时间、授权和同源内容组；处理高相似统计模板家族。", "3. 依中文 60 / 英文 60 的目标按领域、体裁、长度选 120 篇，开发 20 / 正式 100；两语言分别报告。候选数量不能保证这些配额已经满足。", "4. 编写真正覆盖理解操作的问题及完整证据链，独立复核后冻结；当前候选不含正式参考答案，不能直接用于排名。", ""])
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": audit["status"], "counts": counts, "language": by_language, "errors": audit["error_counts"], "flags": audit["flag_counts"], "near_duplicate_pairs": len(audit["near_duplicate_pairs"])}, ensure_ascii=False))
    return 0 if counts["technical_integrity_reject"] == 0 and not manifest_mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
