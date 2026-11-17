"""Install and freeze the approved 2024 model suite in this project's Ollama.

Run on the server from the project root. Downloads weights only through the
already isolated loopback Ollama. Existing models and run records are retained.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUITE = [
    {"id": "qwen25-15b", "name": "Qwen2.5 · 1.5B Instruct", "model": "qwen2.5:1.5b-instruct-q4_K_M", "digest": "65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b", "repo": "Qwen/Qwen2.5-1.5B-Instruct", "revision": "989aa7980e4cf806f80c7fef2b1adb7bc71aa306", "release_date": "2024-09-19"},
    {"id": "qwen25-3b", "name": "Qwen2.5 · 3B Instruct", "model": "qwen2.5:3b-instruct-q4_K_M", "digest": "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b", "repo": "Qwen/Qwen2.5-3B-Instruct", "revision": "aa8e72537993ba99e69dfaafa59ed015b17504d1", "release_date": "2024-09-19"},
    {"id": "qwen25-7b", "name": "Qwen2.5 · 7B Instruct", "model": "qwen2.5:7b-instruct", "digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e", "repo": "Qwen/Qwen2.5-7B-Instruct", "revision": "a09a35458c702b33eeacc393d103063234e8bc28", "release_date": "2024-09-19"},
    {"id": "qwen25-14b", "name": "Qwen2.5 · 14B Instruct", "model": "qwen2.5:14b-instruct-q4_K_M", "digest": "7cdf5a0187d5c58cc5d369b255592f7841d1c4696d45a8c8a9489440385b22f6", "repo": "Qwen/Qwen2.5-14B-Instruct", "revision": "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8", "release_date": "2024-09-19"},
    {"id": "mistral03-7b", "name": "Mistral · 7B Instruct v0.3", "model": "mistral:7b-instruct-v0.3-q4_K_M", "digest": "6577803aa9a036369e481d648a2baebb381ebc6e897f2bb9a766a2aa7bfbc1cf", "repo": "mistralai/Mistral-7B-Instruct-v0.3", "revision": "c170c708c41dac9275d15a8fff4eca08d52bab71", "release_date": "2024-05-22"},
    {"id": "internlm25-7b", "name": "InternLM2.5 · 7B Chat", "model": "internlm2:7b-chat-v2.5-q4_K_M", "digest": "aa0c9b808286311ca91e6c5f200f77be95b7c7c1428211d4fbb791358e02d06b", "repo": "internlm/internlm2_5-7b-chat", "revision": "eb72b541689b0432dade0435feb339b89fdd39ff", "release_date": "2024-07-03"},
    {"id": "llama31-8b", "name": "Llama 3.1 · 8B Instruct", "model": "llama3.1:8b-instruct-q4_K_M", "digest": "46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e", "repo": "meta-llama/Llama-3.1-8B-Instruct", "revision": None, "release_date": "2024-07-23"},
]


def request(base: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def pull(base: str, name: str) -> None:
    req = urllib.request.Request(base + "/api/pull", data=json.dumps({"model": name, "stream": True}).encode(), headers={"Content-Type": "application/json"})
    last_print = 0.0
    success = False
    with urllib.request.urlopen(req, timeout=600) as response:
        for line in response:
            event = json.loads(line)
            if event.get("error"):
                raise ValueError(event["error"])
            if time.monotonic() - last_print > 20 or event.get("status") == "success":
                print(json.dumps({"model": name, **event}), flush=True)
                last_print = time.monotonic()
            success |= event.get("status") == "success"
    if not success:
        raise RuntimeError("Pull ended without success: " + name)


def freeze_qwen(item: dict) -> dict:
    folder = ROOT / "runtime" / "tokenizers" / (item["id"] + "-" + item["revision"][:7])
    if item["id"] == "qwen25-7b":
        folder = ROOT / "runtime" / "tokenizers" / "qwen25-7b-a09a354"
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        # Explicit tokenizer-only immutable-revision downloader from the project.
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "freeze_tokenizer.py"), "--repo", item["repo"], "--revision", item["revision"], "--dest", str(folder)], check=True)
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest["repo_id"] != item["repo"] or manifest["revision"] != item["revision"]:
        raise ValueError("Existing tokenizer identity mismatch")
    for filename, record in manifest["files"].items():
        expected = record["sha256"] if isinstance(record, dict) else record
        if hashlib.sha256((folder / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("Existing tokenizer file hash mismatch")
    return {"tokenizer_spec": {"repo_id": item["repo"], "revision": item["revision"], "artifact_dir": str(folder), "manifest_sha256": hashlib.sha256(raw).hexdigest()}, "runtime_template_kind": "raw_rendered_prompt", "token_budget_margin": 512}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11435")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "model-suite-20261020" / "installed.json")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    if args.url != "http://127.0.0.1:11435":
        parser.error("This deployment is restricted to the project's isolated Ollama")
    from backend import server
    selected_ids = set(args.only or [item["id"] for item in SUITE])
    if any(r["status"] in {"running", "queued"} and
           selected_ids.intersection(r["config"]["model_ids"])
           for r in server.all_objects("run")):
        raise RuntimeError("Selected model belongs to an active run: do not change its configuration")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {"recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "client_date": "2026-10-20", "models_directory": "/home/jmy/reading-bench/runtime/models", "ollama_version": request(args.url, "/api/version"), "policy": "7 historical 2024 models; Q4_K_M; exploratory AI-draft development; distribution digest does not independently prove conversion lineage", "models": [], "errors": []}
    for item in SUITE:
        if args.only and item["id"] not in args.only:
            continue
        try:
            tags = {m["name"]: m for m in request(args.url, "/api/tags")["models"]}
            if item["model"] not in tags:
                pull(args.url, item["model"])
                tags = {m["name"]: m for m in request(args.url, "/api/tags")["models"]}
            installed = tags[item["model"]]
            if item["digest"] and installed["digest"] != item["digest"]:
                raise ValueError("Actual manifest differs from the pre-download fixed digest")
            details = request(args.url, "/api/show", {"model": item["model"]})
            if installed.get("details", {}).get("quantization_level") != "Q4_K_M":
                raise ValueError("Expected Q4_K_M quantization")
            if item.get("weight_blob_sha256"):
                manifest_file = ROOT / "runtime" / "models" / "manifests" / "hf.co" / "internlm" / "internlm2_5-7b-chat-gguf" / "Q4_K_M"
                manifest = json.loads(manifest_file.read_bytes())
                weight = next(x for x in manifest["layers"] if x["mediaType"] == "application/vnd.ollama.image.model")
                if weight["digest"] != "sha256:" + item["weight_blob_sha256"]:
                    raise ValueError("InternLM official fixed GGUF SHA256 mismatch")
            model = {"id": item["id"], "name": item["name"], "provider": "ollama", "base_url": args.url, "model": item["model"], "api_key_env": "", "release_date": item["release_date"], "release_source": "https://huggingface.co/" + item["repo"], "expected_digest": installed["digest"], "created_at": server.now(), "suite_record": {"original_repo": item["repo"], "original_revision": item["revision"], "distribution_manifest_sha256": installed["digest"], "weight_blob_sha256": item.get("weight_blob_sha256"), "provenance_status": "official_2024_gguf_hash_verified" if item.get("weight_blob_sha256") else "historical_original_checkpoint_known;distribution_conversion_lineage_not_independently_reproduced"}}
            if item["id"].startswith("qwen"):
                model.update(freeze_qwen(item))
            server.put("model", model["id"], model)
            result["models"].append({"config": model, "tags": installed, "show": details, "template_sha256": hashlib.sha256(details.get("template", "").encode()).hexdigest()})
            print(json.dumps({"installed": item["id"], "digest": installed["digest"], "exact_tokenizer": "tokenizer_spec" in model}), flush=True)
        except Exception as exc:
            result["errors"].append({"model": item["id"], "error": str(exc), "type": type(exc).__name__})
            print(json.dumps(result["errors"][-1]), flush=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
