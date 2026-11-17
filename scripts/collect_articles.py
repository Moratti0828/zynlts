#!/usr/bin/env python3
"""Download public source snapshots into isolated, unreviewed candidates.

No third-party dependency. Does not modify data/corpus.json or invent questions.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    {"id": "zh-housing-2025", "url": "https://www.forestry.gov.cn/c/www/szxx/635119.jhtml", "language": "zh"},
    {"id": "zh-data-sharing-2025", "url": "https://www.mee.gov.cn/zcwj/gwywj/202506/t20250604_1120657.shtml", "language": "zh"},
    {"id": "zh-public-video-2025", "url": "https://www.mee.gov.cn/zcwj/gwywj/202502/t20250211_1102044.shtml", "language": "zh"},
    {"id": "en-bennu-2025", "url": "https://www.nasa.gov/news-release/nasas-asteroid-bennu-sample-reveals-mix-of-lifes-ingredients/", "language": "en"},
    {"id": "en-nisar-2025", "url": "https://www.nasa.gov/news-release/nasa-isro-satellite-lifts-off-to-track-earths-changing-surfaces/", "language": "en"},
    {"id": "en-comet-2026", "url": "https://science.nasa.gov/blogs/3iatlas/2026/02/04/nasas-spherex-mission-tracks-brightening-of-interstellar-comet/", "language": "en"},
    {"id": "zh-market-supervision-2026", "url": "https://www.mee.gov.cn/zcwj/gwywj/202609/t20260911_1165970.shtml", "language": "zh"},
    {"id": "en-brown-dwarfs-2026", "url": "https://www.nasa.gov/missions/spherex/nasas-spherex-telescope-sees-menagerie-of-brown-dwarfs/", "language": "en"},
]


class VisibleText(HTMLParser):
    """Preserve readable blocks; the full page still needs editorial review."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1
        if not self.hidden and tag in {"p", "div", "h1", "h2", "h3", "br", "li", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in {"p", "div", "h1", "h2", "h3", "li", "article"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

    def text(self):
        lines = [re.sub(r"[\t \u3000\xa0]+", " ", s).strip() for s in "".join(self.parts).splitlines()]
        return "\n".join(s for s in lines if s)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture(source: dict, output: Path) -> dict:
    request = Request(source["url"], headers={"User-Agent": "ReadingBench/1.0 (academic source provenance collection)"})
    with urlopen(request, timeout=45) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP {response.status}")
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Source exceeds 8 MiB; refused truncated capture")
        charset = response.headers.get_content_charset() or "utf-8"
        resolved_url = response.geturl()
        headers = {k: v for k, v in response.headers.items() if k.lower() in {"content-type", "last-modified", "etag"}}
    html = raw.decode(charset, errors="strict")
    parser = VisibleText()
    parser.feed(html)
    extracted = parser.text()
    if len(extracted) < 100:
        raise ValueError("Insufficient text: likely a challenge/redirect page; review required")
    output.mkdir(parents=True, exist_ok=True)
    stem = output / source["id"]
    stem.with_suffix(".html").write_bytes(raw)
    stem.with_suffix(".txt").write_text(extracted, encoding="utf-8")
    metadata = {
        **source, "resolved_url": resolved_url,
        "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "raw_sha256": sha256(raw), "extracted_sha256": sha256(extracted.encode("utf-8")),
        "bytes": len(raw), "charset": charset, "http_headers": headers,
        "reviewed": False, "notice": "Unreviewed snapshot; not automatically admitted to corpus.",
    }
    stem.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New snapshot directory; defaults to data/candidates/<UTC timestamp>")
    parser.add_argument("--id", action="append", dest="ids", help="Capture selected source ID(s)")
    args = parser.parse_args()
    output = args.output or ROOT / "data" / "candidates" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = output.resolve()
    if output == (ROOT / "data").resolve() or output == (ROOT / "data" / "raw").resolve():
        parser.error("Use a new subdirectory, not data/ or data/raw/ directly")
    if output.exists() and any(output.iterdir()):
        parser.error("Output directory is not empty; existing snapshots are immutable")
    selected = [s for s in SOURCES if not args.ids or s["id"] in args.ids]
    if not selected or (args.ids and set(args.ids) - {s["id"] for s in SOURCES}):
        parser.error("Unknown source ID")
    successes, failures = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(capture, s, output): s for s in selected}
        for future in concurrent.futures.as_completed(pending):
            source = pending[future]
            try:
                successes.append(future.result())
                print(f"Captured {source['id']}")
            except Exception as exc:
                failures.append({"id": source["id"], "error": str(exc)})
                print(f"FAILED {source['id']}: {exc}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "capture-manifest.json").write_text(json.dumps({"captures": successes, "failures": failures}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Snapshots: {output}; reviewed corpus unchanged")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
