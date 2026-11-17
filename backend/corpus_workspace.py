"""Read-only view of downloaded source candidates; never promotes them to runs."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATES = ("candidate", "ai_checked", "human_reviewed", "frozen")
PUBLIC_FIELDS = (
    "id", "title", "language", "provider", "source_name", "source_url",
    "source_attribution", "published_at", "first_published_at", "date_evidence",
    "date_review_note", "recency_tier", "domain_provisional", "genre_provisional",
    "rights", "scope", "extraction_selector", "sha256", "raw_sha256", "body_bytes",
    "word_count", "han_count", "downloaded_at", "review_note",
)


def _json(path, limit=50_000_000):
    if path.stat().st_size > limit:
        raise ValueError("候选清单超过读取限制")
    return json.loads(path.read_text(encoding="utf-8"))


def _body(record, root):
    """Only UTF-8 text under the candidate directory is accessible."""
    value = record.get("text_path")
    if not isinstance(value, str) or not value:
        raise ValueError("候选正文文件未声明")
    path = (root / value).resolve()
    boundary = (root / "data" / "candidates").resolve()
    if not path.is_relative_to(boundary) or path.suffix.lower() != ".txt":
        raise ValueError("候选正文路径无效")
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("候选正文缺失或过大")
    text = path.read_text(encoding="utf-8")
    # The collector appends one final LF when writing the snapshot.
    if text.endswith("\n"):
        text = text[:-1]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", ""))) or digest != record["sha256"]:
        raise ValueError("候选正文 hash 与采集记录不一致")
    return text


def _records(root):
    boundary = (root / "data" / "candidates").resolve()
    records, warnings, pools = [], [], []
    if not boundary.exists():
        return records, warnings, pools
    for folder in sorted(boundary.iterdir()):
        if not folder.is_dir() or not folder.resolve().is_relative_to(boundary):
            continue
        manifest = folder / "source-discovery.json"
        try:
            if manifest.exists():
                payload = _json(manifest)
                captures = payload.get("captures", [])
                if not isinstance(captures, list):
                    raise ValueError("captures 格式无效")
                pools.append({"name": folder.name, "status": "collection_complete", "created_at": payload.get("created_at"), "date_window": payload.get("date_window", {})})
            else:
                captures = [_json(p, limit=2_500_000) for p in sorted((folder / "snapshots").glob("*.metadata.json"))]
                if not captures:
                    continue
                pools.append({"name": folder.name, "status": "collecting"})
            for item in captures[:3000]:
                if not isinstance(item, dict) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", str(item.get("id", ""))):
                    warnings.append("一条候选记录缺少有效 ID，已跳过。")
                    continue
                records.append((item, folder.name))
        except (OSError, ValueError, TypeError):
            warnings.append(f"候选池 {folder.name} 暂未形成可读取的清单。")
    # A recapture is not a new article. Match both stable ID and exact body hash.
    unique, ids, hashes = [], set(), set()
    for item, pool in records:
        if item["id"] in ids or item.get("sha256") in hashes:
            continue
        ids.add(item["id"])
        hashes.add(item.get("sha256"))
        unique.append((item, pool))
    return unique, warnings, pools


def benchmark_spec(root=ROOT):
    path = Path(root) / "data" / "benchmark-spec-v2.json"
    if not path.exists():
        return {}
    payload = _json(path, limit=1_000_000)
    return payload if isinstance(payload, dict) else {}


def _public(record, pool, root):
    item = {key: record.get(key) for key in PUBLIC_FIELDS}
    # reviewed=true in old demo imports is not an independent human review.
    item["annotation_status"] = record.get("annotation_status") if record.get("annotation_status") in STATES else "candidate"
    item["pool"] = pool
    item["questions_count"] = len(record.get("questions", [])) if isinstance(record.get("questions"), list) else 0
    item["runnable"] = False
    try:
        text = _body(record, root)
        item.update(body_available=True, hash_verified=True, character_count=len(text))
    except (OSError, ValueError, UnicodeError) as exc:
        item.update(body_available=False, hash_verified=False, body_error=str(exc))
    return item


def _annotations(root):
    """Only explicitly named v2 authoring banks, never scorer fixture records."""
    boundary = (root / "data" / "annotation").resolve()
    articles, workspaces = [], []
    if not boundary.exists():
        return articles, workspaces
    seen = set()
    # Schema, rather than a filename suffix, determines a v2 annotation bank.
    # Dated banks produced by the authoring workflow must be discoverable too.
    for path in sorted(boundary.glob("*.json")):
        if "fixture" in path.name.lower() or not path.resolve().is_relative_to(boundary):
            continue
        try:
            bank = _json(path, limit=5_000_000)
            if bank.get("schema_version") != "reading-bank-v2" or not isinstance(bank.get("articles"), list):
                continue
            # This workspace tracks newly authored candidate-source questions.
            # Public legacy reference passages and union views stay available
            # in experiments but must not inflate recent authoring progress.
            if bank.get("annotation_origin") == "external_public_benchmark" or bank.get("collection_view"):
                continue
            items = []
            for article in bank["articles"]:
                if not isinstance(article, dict) or not isinstance(article.get("paragraphs"), list) or not isinstance(article.get("questions"), list):
                    continue
                if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", str(article.get("source_cluster_id", ""))) or article.get("id") in seen:
                    continue
                seen.add(article["id"])
                articles.append((article, bank, path.name))
                items.append({"id": article["id"], "source_cluster_id": article["source_cluster_id"], "title": article.get("title"), "language": article.get("language"), "questions": len(article["questions"]), "annotation_state": article.get("annotation_state")})
            workspaces.append({"file": path.name, "bank_version": bank.get("bank_version"), "formal": bank.get("formal") is True, "note": bank.get("note"), "articles": items})
        except (OSError, ValueError, TypeError):
            continue
    return articles, workspaces


def _annotation_preview(article, bank, filename, source):
    fields = ("id", "title", "language", "source_cluster_id", "scope", "scope_note", "split", "domain", "annotation_state", "human_review_count", "presented_text_sha256", "source_text_sha256", "paragraphs")
    question_fields = ("id", "dimension", "kind", "prompt", "options", "correct_option", "answers", "value", "unit", "absolute_tolerance", "evidence_sets", "missing_information", "rubric_note", "annotation_state")
    preview = {field: article.get(field) for field in fields}
    preview["questions"] = [{key: q.get(key) for key in question_fields if key in q} for q in article["questions"] if isinstance(q, dict)]
    preview.update(bank_version=bank.get("bank_version"), workspace_file=filename, formal=False, note=bank.get("note"), source_hash_matches=article.get("source_text_sha256") == source.get("sha256"))
    return preview


def workspace_summary(root=ROOT):
    root = Path(root)
    records, warnings, pools = _records(root)
    articles = [_public(record, pool, root) for record, pool in records]
    annotations, annotation_workspaces = _annotations(root)
    annotation_counts = {"articles": len(annotations), "questions": sum(len(a["questions"]) for a, _, _ in annotations), "human_reviewed_articles": sum(a.get("annotation_state") == "human_reviewed" for a, _, _ in annotations), "frozen_articles": sum(a.get("annotation_state") == "frozen" for a, _, _ in annotations), "human_reviewed_questions": sum(q.get("annotation_state") == "human_reviewed" for a, _, _ in annotations for q in a["questions"] if isinstance(q, dict)), "frozen_questions": sum(q.get("annotation_state") == "frozen" for a, _, _ in annotations for q in a["questions"] if isinstance(q, dict))}
    for article in articles:
        article["annotation_question_count"] = sum(len(a["questions"]) for a, _, _ in annotations if a["source_cluster_id"] == article["id"])
    counts = {"total": len(articles), "downloaded": sum(a["body_available"] for a in articles), "language": {"zh": 0, "en": 0}, "states": {s: 0 for s in STATES}, "questions": sum(a["questions_count"] for a in articles), "runnable": 0}
    for article in articles:
        counts["language"][article.get("language") or "unknown"] = counts["language"].get(article.get("language") or "unknown", 0) + 1
        counts["states"][article["annotation_status"]] += 1
    return {"counts": counts, "articles": articles, "pools": pools, "warnings": warnings, "annotation_counts": annotation_counts, "annotation_workspaces": annotation_workspaces, "spec": benchmark_spec(root), "notice": "这些是已下载的待审正文候选。数量不等于正式题库规模；需要独立性、首发日期、许可、正文及题目审定。候选不会进入现有测评接口。"}


def workspace_article(identity, root=ROOT):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", identity):
        raise ValueError("候选 ID 无效")
    root = Path(root)
    records, _, _ = _records(root)
    for record, pool in records:
        if record["id"] == identity:
            item = _public(record, pool, root)
            item["text"] = _body(record, root)
            item["paragraphs"] = [{"id": f"p{index + 1:03d}", "text": paragraph} for index, paragraph in enumerate(item["text"].split("\n\n")) if paragraph.strip()]
            item["paragraph_note"] = "当前段落编号用于浏览，正式标注需在清理正文后重新锁定文章版本与稳定 ID。"
            annotations, _ = _annotations(root)
            item["annotation_preview"] = [_annotation_preview(a, bank, filename, record) for a, bank, filename in annotations if a["source_cluster_id"] == identity]
            return item
    raise ValueError("候选文章不存在")
