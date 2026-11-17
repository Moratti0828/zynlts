"""Record Ollama model digests/runtime metadata, or verify a prior capture.

This verifies unchanged local files. It does not authenticate original weight
provenance, training dates, or the absence of data contamination.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.error
import urllib.request


DEFAULT_MODELS = ["qwen2.5:7b-instruct", "llama3.1:8b-instruct-q4_K_M"]


def fetch(base, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base.rstrip("/") + path, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, default=Path("deploy/model-manifest.json"))
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--verify", type=Path, help="Compare with an existing manifest; do not write a new one.")
    args = parser.parse_args()
    try:
        tags = fetch(args.url, "/api/tags")
        version = fetch(args.url, "/api/version")
        entries = {entry["name"]: entry for entry in tags.get("models", [])}
        selected = []
        for model in args.models:
            if model not in entries:
                raise ValueError(f"Required model not found: {model}")
            selected.append({"name": model, "digest": entries[model]["digest"],
                             "tags_metadata": entries[model],
                             "show_metadata": fetch(args.url, "/api/show", {"model": model})})
        manifest = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "ollama_url": args.url, "ollama_version": version,
                    "provenance_status": "unverified; bind to official fixed checkpoint before formal evaluation",
                    "models": selected}
        if args.verify:
            previous = json.loads(args.verify.read_text(encoding="utf-8-sig"))
            expected = {model["name"]: model["digest"] for model in previous["models"]}
            current = {model["name"]: model["digest"] for model in selected}
            if current != expected:
                raise ValueError("Model set or digest differs from the frozen manifest; benchmark must stop.")
            if previous.get("ollama_version") != version:
                raise ValueError("Ollama runtime version changed; review and freeze a new experiment version.")
            old_shows = {model["name"]: model.get("show_metadata") for model in previous["models"]}
            new_shows = {model["name"]: model.get("show_metadata") for model in selected}
            if old_shows != new_shows:
                raise ValueError("Model/template metadata changed; review before a formal run.")
            print("Verified: model digests, template metadata, and Ollama runtime version are unchanged.")
            return
        if args.output.exists():
            raise ValueError(f"Preserving existing manifest: {args.output}. Choose another --output, or --verify it.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(manifest, output, ensure_ascii=False, indent=2)
            output.write("\n")
        print(f"Recorded {len(selected)} models: {args.output.resolve()}")
        for model in selected:
            print(f"{model['name']} sha256:{model['digest']}")
    except (OSError, ValueError, KeyError, urllib.error.HTTPError) as exc:
        raise SystemExit(f"Model manifest failed: {exc}") from exc


if __name__ == "__main__":
    main()
