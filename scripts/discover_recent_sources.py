#!/usr/bin/env python3
"""Collect dated, substantive source-text candidates, never reviewed questions.

Requires beautifulsoup4 (available in the bundled desktop Python runtime).
Raw responses, exact article-body paragraphs and provenance are immutable.
This script does not modify the reviewed/demo corpus or generate gold answers.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import posixpath
import re
import threading
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
UA = "ReadingBench/2.0 (academic article provenance collection; local research candidates)"
LIMIT = 8 * 1024 * 1024
HOST_LIMITS: dict[str, threading.Semaphore] = {}
HOST_LOCK = threading.Lock()

PRIVATE_ZH = "机构官网新闻不自动属于公有领域。仅作为本地、私有的教学科研候选；保留署名及出处。公开分发全文或题库前须逐篇核实授权；转载、照片、第三方引语须单独审查。"
US_TEXT = "美国联邦机构工作人员原创文字通常适用17 USC 105；本候选仍待核作者及第三方权利。照片、媒体、文学引文、第三方投稿不自动获得许可；当前仅本地私有教学科研使用。"
OGL = "GOV.UK内容一般适用Open Government Licence v3.0，须署名，且不覆盖徽标、个人信息及第三方权利；当前候选须逐篇排除第三方引文和媒体后才能公开分发。"

CONFIG = {
    "cas": {"name": "中国科学院", "language": "zh", "domain": "science_technology", "genre": "research_explanation", "rights": PRIVATE_ZH,
            "lists": ["https://www.cas.cn/syky/", *[f"https://www.cas.cn/syky/index_{i}.shtml" for i in range(1, 6)]],
            "match": r"/syky/2026\d{2}/t\d{8}_\d+\.shtml$", "selectors": [".TRS_UEDITOR", ".TRS_Editor", ".ykjj_txt"]},
    "nbs": {"name": "国家统计局", "language": "zh", "domain": "economy_society", "genre": "statistical_report", "rights": PRIVATE_ZH,
            "lists": ["https://www.stats.gov.cn/sj/zxfb/", *[f"https://www.stats.gov.cn/sj/zxfb/index_{i}.html" for i in range(1, 7)]],
            "match": r"/sj/zxfb/2026\d{2}/t\d{8}_\d+\.html$", "selectors": [".TRS_UEDITOR", ".TRS_Editor", ".txt-content"]},
    "moe": {"name": "中华人民共和国教育部", "language": "zh", "domain": "education_society", "genre": "public_information", "rights": PRIVATE_ZH,
            "lists": ["https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/", *[f"https://www.moe.gov.cn/jyb_xwfb/gzdt_gzdt/index_{i}.html" for i in range(1, 5)]],
            "match": r"/jyb_xwfb/gzdt_gzdt/[^?#]*2026\d{2}/t\d{8}_\d+\.html$", "selectors": [".TRS_Editor", ".TRS_UEDITOR", "#jyb_xwfb_content"]},
    "mct": {"name": "中华人民共和国文化和旅游部", "language": "zh", "domain": "history_culture", "genre": "cultural_news", "rights": PRIVATE_ZH,
            "lists": ["https://www.mct.gov.cn/whzx/whyw/", *[f"https://www.mct.gov.cn/whzx/whyw/index_{i}.htm" for i in range(1, 4)]],
            "match": r"/whzx/whyw/2026\d{2}/t\d{8}_\d+\.htm$", "selectors": [".TRS_Editor", ".TRS_UEDITOR"]},
    "mee": {"name": "中华人民共和国生态环境部", "language": "zh", "domain": "environment", "genre": "environmental_news", "rights": PRIVATE_ZH,
            "lists": ["https://www.mee.gov.cn/ywdt/hjywnews/", *[f"https://www.mee.gov.cn/ywdt/hjywnews/index_{i}.shtml" for i in range(1, 9)]],
            "match": r"/ywdt/hjywnews/2026\d{2}/t\d{8}_\d+\.shtml$", "selectors": [".TRS_Editor", ".TRS_UEDITOR", ".Custom_UnionStyle"]},
    "nih": {"name": "US National Institutes of Health", "language": "en", "domain": "health_life", "genre": "research_explanation", "rights": US_TEXT,
            "lists": ["https://www.nih.gov/news-events/news-releases", *[f"https://www.nih.gov/news-events/news-releases?page={i}" for i in range(1, 6)]],
            "match": r"/news-events/news-releases/[^/?#]+$", "selectors": ["article[data-history-node-id]", "#news-release", ".field--name-body", ".content-area", "#main-content"]},
    "loc": {"name": "US Library of Congress", "language": "en", "domain": "history_culture", "genre": "cultural_narrative", "rights": US_TEXT,
            "lists": ["https://blogs.loc.gov/loc/2026/", *[f"https://blogs.loc.gov/loc/2026/page/{i}/" for i in range(2, 7)]],
            "match": r"/loc/2026/\d{2}/[^/?#]+/$", "selectors": [".entry-content"]},
    "census": {"name": "US Census Bureau", "language": "en", "domain": "economy_society", "genre": "statistical_explanation", "rights": US_TEXT,
            "lists": ["https://www.census.gov/library/stories/2026.html"],
            "match": r"/library/stories/2026/\d{2}/[^/?#]+\.html$", "selectors": [".uscb-main-responsivegrid.uscb-grid-7", ".uscb-story-body", ".uscb-main-content", ".content-main", "main"]},
    "usgs": {"name": "US Geological Survey", "language": "en", "domain": "environment", "genre": "science_explanation", "rights": US_TEXT,
            "lists": ["https://www.usgs.gov/news/featured-stories", *[f"https://www.usgs.gov/news/featured-stories?page={i}" for i in range(1, 5)], "https://www.usgs.gov/news/science-snippets"],
            "match": r"/news/(?:featured-story|science-snippet)/(?!feed$)[^/?#]+$", "selectors": [".field--name--body", ".field--name--field-body", ".field--name-body", ".field--name-field-body", ".node__content"]},
    "nasa": {"name": "US National Aeronautics and Space Administration", "language": "en", "domain": "science_technology", "genre": "science_explanation", "rights": US_TEXT,
             "lists": [], "selectors": []},
    "govuk": {"name": "UK Government (multiple departments)", "language": "en", "domain": "public_policy", "genre": "public_information", "rights": OGL,
              "lists": [], "selectors": []},
}

# Supplementary pools use the same parent institution attribution, rather than
# pretending a different directory is an independent publisher.
CONFIG["cas_health"] = {**CONFIG["cas"], "domain": "health_life", "title_regex": r"药|肿瘤|癌|结肠炎|脑|神经|免疫|衰老|医学|胚胎|疾病|心血管|细胞",
                         "lists": ["https://www.cas.cn/syky/", *[f"https://www.cas.cn/syky/index_{i}.shtml" for i in range(1, 15)]]}
CONFIG["mct_local"] = {**CONFIG["mct"], "domain": "history_culture", "genre": "cultural_narrative",
                       "lists": ["https://www.mct.gov.cn/whzx/qgwhxxlb/"],
                       "match": r"/whzx/qgwhxxlb/[^?#]*2026\d{2}/t\d{8}_\d+\.htm$"}
CONFIG["usgs_release"] = {**CONFIG["usgs"], "genre": "science_news",
                          "lists": ["https://www.usgs.gov/news/news-releases/all-news-releases", *[f"https://www.usgs.gov/news/news-releases/all-news-releases?page={i}" for i in range(1, 5)]],
                          "match": r"/news/(?:national-news-release|state-news-release)/[^/?#]+$"}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_url(url: str) -> str:
    p = urlsplit(url)
    path = posixpath.normpath(p.path)
    if p.path.endswith("/") and not path.endswith("/"):
        path += "/"
    return urlunsplit((p.scheme or "https", p.netloc.lower(), path, p.query, ""))


def fetch(url: str) -> tuple[bytes, dict]:
    host = urlsplit(url).netloc
    with HOST_LOCK:
        semaphore = HOST_LIMITS.setdefault(host, threading.Semaphore(2))
    with semaphore:
        with urlopen(Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.5"}), timeout=35) as response:
            raw = response.read(LIMIT + 1)
            if len(raw) > LIMIT:
                raise ValueError("Response over 8 MiB; refusing a truncated snapshot")
            return raw, {"resolved_url": response.geturl(), "http_status": response.status,
                         "content_type": response.headers.get("Content-Type"), "etag": response.headers.get("ETag"),
                         "last_modified": response.headers.get("Last-Modified"),
                         "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}


def soup(raw: bytes) -> BeautifulSoup:
    return BeautifulSoup(raw, "html.parser")


def normalize_text(value: str) -> str:
    return re.sub(r"[\t \u3000\xa0]+", " ", value).strip()


def iso_date(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"(20\d{2})[\-/年](\d{1,2})[\-/月](\d{1,2})", value)
    if m:
        try:
            return dt.date(*(int(x) for x in m.groups())).isoformat()
        except ValueError:
            return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%A, %B %d, %Y"):
        try:
            return dt.datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}", value)
    if m:
        return dt.datetime.strptime(m.group(), "%B %d, %Y").date().isoformat()
    return None


def paragraphs(body: BeautifulSoup) -> list[str]:
    # Figure captions, script, UI and comments do not belong to the prose passage.
    for element in body.select("script,style,noscript,svg,figure,figcaption,nav,form,.share,.social-media,.related-content,.author_bio,.comments,.hds-topic-cards-wrapper,.hds-news-card"):
        element.decompose()
    result = []
    for element in body.find_all(["h2", "h3", "p", "li", "tr"]):
        if element.find_parent("table") and element.name != "tr":
            continue
        if element.name == "tr":
            text = " | ".join(normalize_text(x.get_text(" ", strip=True)) for x in element.find_all(["th", "td"], recursive=False))
        else:
            text = normalize_text(element.get_text(" ", strip=True))
        if re.match(r"^(Subscribe\b|Connect with Us$|Get an alert directly in your inbox|Contact our Public Information Office|NIH Office of Communications$|\d+\s+min\s+read$|>>>更多内容)", text, re.I):
            continue
        if len(text) >= 10 and text not in result:
            result.append(text)
    if not result:
        result = [normalize_text(x) for x in body.get_text("\n", strip=True).splitlines() if len(normalize_text(x)) >= 10]
    return result


def date_from_html(document: BeautifulSoup, provider: str) -> tuple[str | None, dict]:
    # Publish date is distinct from updated date; URL stamps are never date evidence.
    if provider.startswith("usgs"):
        # USGS article publication is a span in the owner-date header. Global
        # <time> elements belong to related research cards, not this article.
        element = document.select_one(".node-intro .owner-date .date")
        if element and iso_date(element.get_text(" ", strip=True)):
            value = element.get_text(" ", strip=True)
            return iso_date(value), {"kind": "publication_element", "selector": ".node-intro .owner-date .date", "value": value}
        return None, {"kind": "missing_article_owner_date_header", "review_required": True}
    for key in ["PubDate", "publishdate", "dc.date", "DC.date", "article:published_time", "date", "datePublished", "DCTERMS.issued", "DC.Date"]:
        element = document.find("meta", attrs={"name": key}) or document.find("meta", attrs={"property": key})
        if element and iso_date(element.get("content")):
            value = element["content"]
            return iso_date(value), {"kind": "publication_meta", "field": key, "value": value}
    for script in document.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
            stack = [data]
            while stack:
                value = stack.pop()
                if isinstance(value, dict):
                    if iso_date(value.get("datePublished")):
                        return iso_date(value["datePublished"]), {"kind": "json_ld", "field": "datePublished", "value": value["datePublished"]}
                    stack.extend(value.values())
                elif isinstance(value, list):
                    stack.extend(value)
        except (ValueError, TypeError):
            pass
    selectors = {
        "nih": [".nih-pretitle", ".date", ".news-release-date", "#main-content time"],
        "usgs": [".field--name-field-news-release-date", ".field--name-field-release-date", ".field--name-created", "time"],
        "census": [".uscb-release-date", ".uscb-story-date", ".uscb-date", "time"],
    }
    for selector in selectors.get(provider, []) + ["time[datetime]"]:
        for element in document.select(selector):
            raw = element.get("datetime") or element.get_text(" ", strip=True)
            value = iso_date(raw)
            if value:
                return value, {"kind": "publication_element", "selector": selector, "value": raw}
    if provider in {"nih", "census", "usgs"}:
        # Institutional pages have a human-readable publication header. Keep its
        # literal text and location evidence for independent review.
        for element in document.select("main, #main-content, article"):
            text = element.get_text(" ", strip=True)[:1800]
            value = iso_date(text)
            if value:
                m = re.search(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}", text)
                if m:
                    return value, {"kind": "publication_header_text", "selector": "main/article header first 1800 characters", "value": m.group(), "review_required": True}
    return None, {"kind": "missing_publication_date", "review_required": True}


def discover_html(provider: str, list_url: str, output: Path) -> tuple[list[dict], dict]:
    raw, info = fetch(list_url)
    d = soup(raw)
    config = CONFIG[provider]
    links = {}
    for element in d.select("a[href]"):
        url = canonical_url(urljoin(list_url, element["href"]))
        title = normalize_text(element.get_text(" ", strip=True))
        if len(title) >= 12 and re.search(config["match"], url) and (not config.get("title_regex") or re.search(config["title_regex"], title)):
            links.setdefault(url, {"provider": provider, "source_url": url, "discovered_title": title,
                                  "discovery_url": list_url, "discovered_date": iso_date(element.parent.get_text(" ", strip=True))})
    path = output / "discovery-pages" / f"{provider}-{digest(list_url.encode())[:12]}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return list(links.values()), {"provider": provider, "url": list_url, "raw_path": str(path.relative_to(ROOT)).replace("\\", "/"), "raw_sha256": digest(raw), **info, "found": len(links)}


def discover_api(provider: str, args, output: Path) -> tuple[list[dict], list[dict]]:
    found, pages = [], []
    if provider == "nasa":
        urls = ["https://www.nasa.gov/wp-json/wp/v2/posts?" + urlencode({"per_page": 40, "after": args.since + "T00:00:00", "before": args.until + "T23:59:59", "page": page}) for page in range(1, args.api_pages + 1)]
    else:
        organisations = ["department-for-culture-media-and-sport", "department-for-education", "department-of-health-and-social-care", "department-for-environment-food-rural-affairs", "department-for-business-and-trade", "department-for-science-innovation-and-technology", "hm-treasury"]
        urls = ["https://www.gov.uk/api/search.json?" + urlencode({"count": 10, "filter_public_timestamp": "from:" + args.since, "filter_format": "press_release", "filter_organisations": org, "order": "-public_timestamp", "fields": "title,link,public_timestamp,organisations,format"}) for org in organisations]
    for url in urls:
        try:
            raw, info = fetch(url)
            values = json.loads(raw)
            path = output / "discovery-pages" / f"{provider}-{digest(url.encode())[:12]}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            values = values if provider == "nasa" else values["results"]
            for item in values:
                link = item["link"] if provider == "nasa" else urljoin("https://www.gov.uk", item["link"])
                found.append({"provider": provider, "source_url": canonical_url(link), "discovered_title": BeautifulSoup(item["title"]["rendered"], "html.parser").get_text() if provider == "nasa" else item["title"], "discovered_date": iso_date(item.get("date") or item.get("public_timestamp")), "discovery_url": url, "api_item": item if provider == "nasa" else None,
                              "discovery_raw_path": str(path.relative_to(ROOT)).replace("\\", "/"), "discovery_raw_sha256": digest(raw), "discovery_http_info": info})
            pages.append({"provider": provider, "url": url, "raw_path": str(path.relative_to(ROOT)).replace("\\", "/"), "raw_sha256": digest(raw), **info, "found": len(values)})
        except Exception as exc:
            pages.append({"provider": provider, "url": url, "error": str(exc)})
    return found, pages


def capture(candidate: dict, args, output: Path) -> dict:
    provider = candidate["provider"]
    config = CONFIG[provider]
    source_url = candidate["source_url"]
    identifier = f"{config['language']}-{provider}-{digest(source_url.encode())[:12]}"
    api = None
    if provider == "govuk":
        request_url = "https://www.gov.uk/api/content" + urlsplit(source_url).path
        raw, info = fetch(request_url)
        api = json.loads(raw)
        title = api["title"]
        published_at = iso_date(api.get("first_published_at"))
        date_evidence = {"kind": "official_content_api", "field": "first_published_at", "value": api.get("first_published_at"), "updated_at": api.get("public_updated_at")}
        body_html = api.get("details", {}).get("body", "")
        if not isinstance(body_html, str) or not body_html:
            raise ValueError("Content API has no substantive article body")
        body = soup(body_html.encode("utf-8"))
        extraction_selector = "official Content API details.body"
        body_source = None
        raw_suffix = ".api.json"
    elif provider == "nasa":
        api = candidate["api_item"]
        raw = json.dumps(api, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        info = candidate.get("discovery_http_info") or {"resolved_url": candidate["discovery_url"], "http_status": 200, "content_type": "application/json", "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        request_url = candidate["discovery_url"]
        title = soup(api["title"]["rendered"].encode()).get_text()
        published_at = iso_date(api.get("date"))
        date_evidence = {"kind": "official_wordpress_api", "field": "date", "value": api.get("date"), "date_gmt": api.get("date_gmt"), "modified": api.get("modified")}
        body = soup(api["content"]["rendered"].encode("utf-8"))
        extraction_selector = "official Wordpress API content.rendered"
        body_source = None
        raw_suffix = ".api.json"
    else:
        request_url = source_url
        raw, info = fetch(request_url)
        document = soup(raw)
        published_at, date_evidence = date_from_html(document, provider)
        heading = document.find("meta", attrs={"name": "ArticleTitle"}) or document.find("meta", attrs={"property": "og:title"})
        title = heading.get("content") if heading else (document.find("h1").get_text(" ", strip=True) if document.find("h1") else candidate["discovered_title"])
        source_meta = document.find("meta", attrs={"name": "ContentSource"}) or document.find("meta", attrs={"name": "source"})
        body_source = source_meta.get("content") if source_meta else None
        body, extraction_selector = None, None
        for selector in config["selectors"]:
            matches = document.select(selector)
            if matches:
                body = max(matches, key=lambda el: len(el.get_text()))
                extraction_selector = selector
                break
        if provider in {"usgs", "usgs_release"} and document.select(".field-intro,.field-text-with-media"):
            # Storytelling pages split a single narrative over several blocks;
            # merge those prose blocks in DOM order, excluding related cards.
            body = soup("\n".join(str(element) for element in document.select(".field-intro,.field-text-with-media")).encode("utf-8"))
            extraction_selector = "all .field-intro,.field-text-with-media in DOM order"
        if body is None:
            raise ValueError("Institution-specific article-body selector missing; refusing whole-page/navigation extraction")
        raw_suffix = ".html"
    if not published_at:
        raise ValueError("No publication-date evidence; updated dates and URL dates are insufficient")
    if not args.since <= published_at <= args.until:
        raise ValueError(f"Publication date {published_at} outside {args.since}..{args.until}")
    para = paragraphs(body)
    text = "\n\n".join(para)
    word_count = len(re.findall(r"\b[\w'-]+\b", text)) if config["language"] == "en" else None
    han_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if len(para) < 3 or (config["language"] == "zh" and han_count < 350) or (config["language"] == "en" and word_count < 200):
        raise ValueError(f"Insufficient article body: paragraphs={len(para)}, han={han_count}, words={word_count}")
    raw_path = output / "snapshots" / (identifier + raw_suffix)
    text_path = output / "snapshots" / (identifier + ".txt")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(raw)
    text_path.write_text(text + "\n", encoding="utf-8", newline="\n")
    earliest = published_at if provider == "govuk" else None
    record = {
        "id": identifier, "title": title, "language": config["language"], "provider": provider,
        "source_name": config["name"], "source_url": source_url, "request_url": request_url,
        "source_attribution": body_source, "published_at": published_at, "first_published_at": earliest,
        "date_evidence": date_evidence,
        "date_review_note": "Official Content API explicitly records first publication." if earliest else "Official source page/API publication verified; earlier publication or repost elsewhere remains to be checked. Do not equate an URL stamp or update with first publication.",
        "recency_tier": "2026-H2" if published_at >= args.preferred_since else "2026-H1-extension",
        "domain_provisional": config["domain"], "genre_provisional": config["genre"], "rights": config["rights"],
        "scope": "article_body_candidate", "extraction_selector": extraction_selector, "text": text,
        "paragraphs": para, "body_bytes": len(text.encode("utf-8")), "word_count": word_count, "han_count": han_count,
        "sha256": digest(text.encode("utf-8")), "raw_sha256": digest(raw),
        "raw_capture_kind": "parsed_official_api_item" if provider == "nasa" else "http_response_bytes",
        "raw_capture_note": "NASA raw_path is a JSON serialization of one authentic API item; raw_sha256 hashes this item snapshot. The unmodified full HTTP response is discovery_raw_path and has its own hash." if provider == "nasa" else "raw_path preserves unmodified HTTP response bytes.",
        "discovery_raw_path": candidate.get("discovery_raw_path"), "discovery_raw_sha256": candidate.get("discovery_raw_sha256"),
        "raw_path": str(raw_path.relative_to(ROOT)).replace("\\", "/"), "text_path": str(text_path.relative_to(ROOT)).replace("\\", "/"),
        "reviewed": False, "review_note": "真实下载的待审候选。尚无阅读理解题、参考答案或人工审定；不计入正式测评题库。", **info,
    }
    (output / "snapshots" / (identifier + ".metadata.json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/candidates/20261011-source-discovery")
    parser.add_argument("--since", default="2026-01-01")
    parser.add_argument("--preferred-since", default="2026-07-01")
    parser.add_argument("--until", default="2026-10-11")
    parser.add_argument("--max-per-source", type=int, default=35)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--providers", nargs="+", choices=list(CONFIG), default=list(CONFIG))
    parser.add_argument("--exclude-capture-directory", type=Path, action="append", help="Skip URLs already captured in another pool; repeat for multiple pools")
    parser.add_argument("--minimum-total", type=int, default=150)
    parser.add_argument("--minimum-per-language", type=int, default=75)
    parser.add_argument("--api-pages", type=int, default=3, help="NASA official API pages, 40 items each")
    args = parser.parse_args()
    for key in ("since", "preferred_since", "until"):
        dt.date.fromisoformat(getattr(args, key))
    args.output = args.output.resolve()
    if not args.output.is_relative_to(ROOT / "data/candidates"):
        parser.error("Output must be a new directory under project data/candidates")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Nonempty output snapshots are immutable; choose a new output directory")
    args.output.mkdir(parents=True, exist_ok=True)
    found, discovery_pages = [], []
    tasks = [(provider, url) for provider in args.providers for url in CONFIG[provider]["lists"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(discover_html, provider, url, args.output): (provider, url) for provider, url in tasks}
        for future in concurrent.futures.as_completed(pending):
            provider, url = pending[future]
            try:
                links, page = future.result()
                found.extend(links)
                discovery_pages.append(page)
                print(f"Discover {provider}: {len(links)} links", flush=True)
            except Exception as exc:
                discovery_pages.append({"provider": provider, "url": url, "error": str(exc)})
    for provider in args.providers:
        if provider in {"govuk", "nasa"}:
            links, pages = discover_api(provider, args, args.output)
            found.extend(links)
            discovery_pages.extend(pages)
    unique = {}
    for item in found:
        unique.setdefault(item["source_url"], item)
    excluded_urls = set()
    for directory in args.exclude_capture_directory or []:
        for path in directory.glob("*.metadata.json"):
            excluded_urls.add(json.loads(path.read_text(encoding="utf-8"))["source_url"])
    selected = []
    for provider in args.providers:
        candidates = [item for item in unique.values() if item["provider"] == provider and item["source_url"] not in excluded_urls and (not item["discovered_date"] or args.since <= item["discovered_date"] <= args.until)]
        # Recent material first, stable URL ordering for reproducible selection.
        candidates.sort(key=lambda item: (item["discovered_date"] or "2026-12-31", item["source_url"]), reverse=True)
        selected.extend(candidates[:args.max_per_source])
    success, failed = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(capture, item, args, args.output): item for item in selected}
        for future in concurrent.futures.as_completed(pending):
            item = pending[future]
            try:
                success.append(future.result())
                print(f"Capture {len(success)}: {success[-1]['id']} ({success[-1]['body_bytes']} bytes)", flush=True)
            except Exception as exc:
                failed.append({"provider": item["provider"], "source_url": item["source_url"], "error": str(exc)})
    # Exclude byte-identical article bodies; translations and event duplicates
    # still require editorial checks and are not claimed to be independent.
    hashes, accepted, duplicates = set(), [], []
    for item in sorted(success, key=lambda item: item["id"]):
        if item["sha256"] in hashes:
            duplicates.append({"id": item["id"], "reason": "identical normalized article body"})
        else:
            hashes.add(item["sha256"])
            accepted.append(item)
    manifest = {
        "version": "source-candidates-v1", "status": "unreviewed_downloaded_candidates",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "date_window": {"since": args.since, "preferred_since": args.preferred_since, "until": args.until},
        "notice": "文章正文候选已真实下载，但不是完成的120篇题库；尚需授权/首发日期/独立性/正文清理/领域和体裁复核，编题及双人审题。无法以数量代替题库质量。",
        "discovery_pages": discovery_pages, "discovered_unique_urls": len(unique), "selected_for_download": len(selected),
        "counts": {"captures": len(accepted), "language": dict(Counter(item["language"] for item in accepted)),
                   "provider": dict(Counter(item["provider"] for item in accepted)), "recency_tier": dict(Counter(item["recency_tier"] for item in accepted))},
        "captures": accepted, "failures": failed, "duplicates": duplicates,
    }
    target = args.output / "source-discovery.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False), flush=True)
    print(f"Manifest: {target}; current data/corpus.json unchanged", flush=True)
    return 0 if len(accepted) >= args.minimum_total and min(manifest["counts"]["language"].get(k, 0) for k in ["zh", "en"]) >= args.minimum_per_language else 2


if __name__ == "__main__":
    raise SystemExit(main())
