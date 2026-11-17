"""Explicitly fetch two immutable tokenizer files; never model weights.

Example (run from reading-bench):
    python scripts/freeze_tokenizer.py --repo Qwen/Qwen2.5-7B-Instruct \
      --revision a09a35458c702b33eeacc393d103063234e8bc28 \
      --dest runtime/tokenizers/qwen25-7b-a09a354

Dependencies are not installed. The completed destination is immutable to this
script: use a new directory for a new snapshot, never silently replace one.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 32 * 1024 * 1024
REPO_PATTERN = re.compile(r"Qwen/Qwen2\.5-(?:0\.5|1\.5|3|7|14|32|72)B-Instruct\Z")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--dest", required=True)
    args = parser.parse_args()
    if not REPO_PATTERN.fullmatch(args.repo) or not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        parser.error("Use a supported Qwen2.5 Instruct repository and an immutable 40-character revision")
    destination = Path(args.dest).expanduser()
    if not destination.is_absolute():
        destination = PROJECT_ROOT / destination
    destination = destination.resolve()
    if destination.exists():
        parser.error("Destination exists; use a new snapshot directory instead of overwriting frozen files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    downloaded = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest = {"schema_version": "reading-tokenizer-v1", "repo_id": args.repo,
                "revision": args.revision, "downloaded_at": downloaded,
                "note": "Explicit tokenizer-only download; no model weights or automatic dependency installation",
                "files": {}}
    with tempfile.TemporaryDirectory(prefix=".tokenizer-freeze-", dir=destination.parent) as temporary:
        staging = Path(temporary).resolve()
        # Validate the exact staged and final paths before any directory move.
        if staging.parent != destination.parent or destination == destination.parent:
            raise ValueError("Snapshot staging path is outside the explicit destination parent")
        for filename in ("tokenizer.json", "tokenizer_config.json"):
            url = f"https://huggingface.co/{args.repo}/resolve/{args.revision}/{filename}"
            request = urllib.request.Request(url, headers={"User-Agent": "ReadingBench-TokenizerSnapshot/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response:
                data = response.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError(f"Tokenizer file exceeds the 32 MiB safety limit: {filename}")
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValueError(f"Expected a JSON object in {filename}")
            if filename == "tokenizer_config.json" and not isinstance(parsed.get("chat_template"), str):
                raise ValueError("This snapshot needs a single string chat_template")
            (staging / filename).write_bytes(data)
            manifest["files"][filename] = {"sha256": hashlib.sha256(data).hexdigest(),
                                           "bytes": len(data), "source_url": url}
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (staging / "manifest.json").write_bytes(manifest_bytes)
        # A completed snapshot only becomes visible after both files validate.
        if destination.exists():
            raise ValueError("Destination was created concurrently; frozen files were not overwritten")
        staging.rename(destination)
    spec = {"repo_id": args.repo, "revision": args.revision, "artifact_dir": str(destination),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest()}
    print(json.dumps({"tokenizer_spec": spec, "runtime_template_kind": "raw_rendered_prompt",
                      "token_budget_margin": 512, "downloaded_model_weights": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
