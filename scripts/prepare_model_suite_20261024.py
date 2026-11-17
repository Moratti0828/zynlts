"""Install three fixed historical models on the project's server only.

The tokenizer-only mode may run on the workstation and downloads no weights.
Model pull, full blob hashing and registration require the named server root.
No inference, dependency installation, gated login, click-through action or old-ID updates.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = Path("/home/jmy/reading-bench")
BASE_URL = "http://127.0.0.1:11435"
METADATA = ROOT / "output/model-suite-20261024/metadata"
YI_REVISION = "771924d1c83d67527d665913415d7086f11ea9c0"
SUITE = [
    {"id": "gemma2-9b", "name": "Gemma 2 · 9B Instruct", "model": "gemma2:9b-instruct-q4_K_M",
     "digest": "c20bec88025f3aefa420efd64dca0ee4abc8e36078d6b74b0f660cdcbd5d1982",
     "weight_blob_sha256": "cb654129f57b4f44e372fab3d6540c0d6784c3adc33125d7c38ab47122ee2a54",
     "repo": "google/gemma-2-9b-it", "revision": "11c9b309abf73637e4b6f9a3fa1e92e615547819",
     "release_date": "2024-06-27", "release_source": "https://blog.google/technology/developers/google-gemma-2/",
     "release_date_basis": "official Google launch article datePublished=2024-06-27",
     "native_context_tokens": 8192, "total_parameters": 9241705984,
     "architecture": "Gemma2ForCausalLM", "license": "Gemma Terms of Use (custom)",
     "language_coverage": "Official model card describes English; Chinese results exploratory",
     "metadata_prefix": "gemma2"},
    {"id": "phi35-mini", "name": "Phi-3.5 · Mini Instruct (3.8B)", "model": "phi3.5:3.8b-mini-instruct-q4_K_M",
     "digest": "57096159698481b47ea17995d1a71f28eea1e26fc801df39a841b29badb4aa63",
     "weight_blob_sha256": "3ef532675b6684b28e0a1a0dca8b3bf4132673bf2294b7d87b41b1d64bb03bca",
     "repo": "microsoft/Phi-3.5-mini-instruct", "revision": "af0dfb8029e8a74545d0736d30cb6b58d2f0f3f0",
     "release_date": "2024-08-20",
     "release_source": "https://huggingface.co/microsoft/Phi-3.5-mini-instruct/commit/d509c5617b2dd9fcdc75022aad9382c4bc8e8b54",
     "release_date_basis": "author model card published 2024-08-20; conservative known-public upper bound, not exact training end",
     "native_context_tokens": 131072, "total_parameters": 3821079552,
     "architecture": "Phi3ForCausalLM", "license": "MIT",
     "language_coverage": "Official 2024 card lists English and Chinese among 23 supported languages; quality differs by language",
     "metadata_prefix": "phi35"},
    {"id": "yi15-6b", "name": "Yi-1.5 · 6B Chat", "model": "yi:6b-chat-v1.5-q4_K_M",
     "digest": "fa152930bd7fba7d9c42c1544a3538eb219873dc4a39d0036ecd0253948998c0",
     "weight_blob_sha256": "79bc28516580c9da278d14b8dbcfa2761dc99ccc2e905e1b31c786dc5f866fd1",
     "repo": "01-ai/Yi-1.5-6B-Chat", "revision": YI_REVISION,
     "release_date": "2024-08-27",
     "release_source": "https://huggingface.co/01-ai/Yi-1.5-6B-Chat/commit/" + YI_REVISION,
     "release_date_basis": "fixed author snapshot committed 2024-08-27; conservative known-public upper bound, not first release date",
     "native_context_tokens": 4096, "total_parameters": 6061035520,
     "architecture": "LlamaForCausalLM", "license": "Apache-2.0",
     "language_coverage": "Yi family is Chinese/English bilingual; task performance still measured separately",
     "metadata_prefix": "yi15"},
]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def request_json(url: str, body: dict | None = None, timeout: int = 30) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def assert_server_location(root: Path, platform: str) -> None:
    if platform != "linux" or root.resolve() != SERVER_ROOT:
        raise ValueError("Weight downloads/registration only allowed at /home/jmy/reading-bench on Linux; use --freeze-tokenizer-only for workstation small files")


def fixed_manifest(item: dict) -> dict:
    library, tag = item["model"].split(":", 1)
    url = f"https://registry.ollama.ai/v2/library/{library}/manifests/{tag}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json", "User-Agent": "ReadingBench-Metadata/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != item["digest"]:
        raise ValueError("Registry tag changed since pre-download freeze; refuse pull: " + item["id"])
    manifest = json.loads(raw)
    weights = [layer for layer in manifest["layers"] if layer["mediaType"] == "application/vnd.ollama.image.model"]
    if len(weights) != 1 or weights[0]["digest"] != "sha256:" + item["weight_blob_sha256"]:
        raise ValueError("Pinned GGUF layer differs")
    METADATA.mkdir(parents=True, exist_ok=True)
    target = METADATA / (item["metadata_prefix"] + "-manifest.json")
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Existing source snapshot differs; frozen metadata was not overwritten")
    target.write_bytes(raw)
    return manifest


def pull(base: str, name: str) -> None:
    """Ollama's content-addressed pull can resume existing partial blobs."""
    request = urllib.request.Request(base + "/api/pull", data=json.dumps({"model": name, "stream": True}).encode(), headers={"Content-Type": "application/json"})
    success, last_print = False, 0.0
    with urllib.request.urlopen(request, timeout=600) as response:
        for line in response:
            event = json.loads(line)
            if event.get("error"):
                raise ValueError(event["error"])
            success |= event.get("status") == "success"
            if time.monotonic() - last_print >= 20 or event.get("status") == "success":
                print(json.dumps({"model": name, **event}), flush=True)
                last_print = time.monotonic()
    if not success:
        raise ValueError("Pull stream ended without success")


def verify_blobs(models_dir: Path, item: dict, manifest: dict) -> list[dict]:
    library, tag = item["model"].split(":", 1)
    manifest_path = models_dir / "manifests/registry.ollama.ai/library" / library / tag
    if sha_file(manifest_path) != item["digest"]:
        raise ValueError("Installed manifest file SHA mismatch")
    verified = []
    for layer in [manifest["config"], *manifest["layers"]]:
        expected = layer["digest"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
            raise ValueError("Unexpected blob digest format")
        path = models_dir / "blobs" / expected.replace(":", "-", 1)
        if path.stat().st_size != layer["size"] or sha_file(path) != expected[7:]:
            raise ValueError("Installed blob full SHA/size mismatch: " + path.name)
        verified.append({"mediaType": layer["mediaType"], "bytes": layer["size"], "sha256": expected[7:]})
    return verified


def freeze_yi_tokenizer(destination: Path) -> dict:
    """Two author tokenizer files only; completed snapshots never replaced."""
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix=".yi-tokenizer-", dir=destination.parent) as directory:
            staging = Path(directory).resolve()
            manifest = {"schema_version": "reading-tokenizer-v1", "repo_id": "01-ai/Yi-1.5-6B-Chat", "revision": YI_REVISION,
                        "downloaded_at": now(), "note": "Explicit tokenizer-only snapshot; no weights; native adapter requires separate runtime validation", "files": {}}
            for name in ("tokenizer.json", "tokenizer_config.json"):
                url = f"https://huggingface.co/01-ai/Yi-1.5-6B-Chat/resolve/{YI_REVISION}/{name}"
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ReadingBench-TokenizerSnapshot/1.0"}), timeout=45) as response:
                    data = response.read(32 * 1024 * 1024 + 1)
                if len(data) > 32 * 1024 * 1024 or not isinstance(json.loads(data), dict):
                    raise ValueError("Invalid/oversized tokenizer JSON: " + name)
                (staging / name).write_bytes(data)
                manifest["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "source_url": url}
            config = json.loads((staging / "tokenizer_config.json").read_bytes())
            if not isinstance(config.get("chat_template"), str):
                raise ValueError("Expected author native string template")
            atomic_json(staging / "manifest.json", manifest)
            if staging.parent != destination.parent or destination.exists():
                raise ValueError("Snapshot destination changed; frozen files retained")
            staging.rename(destination)
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("repo_id") != "01-ai/Yi-1.5-6B-Chat" or manifest.get("revision") != YI_REVISION:
        raise ValueError("Existing Yi tokenizer identity mismatch")
    for name in ("tokenizer.json", "tokenizer_config.json"):
        if sha_file(destination / name) != manifest["files"][name]["sha256"]:
            raise ValueError("Existing Yi tokenizer SHA mismatch")
    return {"repo_id": manifest["repo_id"], "revision": YI_REVISION, "artifact_dir": str(destination), "manifest_sha256": sha_file(manifest_path)}


def new_model_record(item: dict, created_at: str) -> dict:
    model = {"id": item["id"], "name": item["name"], "provider": "ollama", "base_url": BASE_URL,
            "model": item["model"], "api_key_env": "", "expected_digest": item["digest"],
            "release_date": item["release_date"], "release_source": item["release_source"],
            "created_at": created_at, "native_context_tokens": item["native_context_tokens"],
            "token_budget_margin": 512,
            "suite_record": {"original_repo": item["repo"], "original_revision": item["revision"],
                "release_date_basis": item["release_date_basis"], "distribution_manifest_sha256": item["digest"],
                "weight_blob_sha256": item["weight_blob_sha256"], "total_parameters": item["total_parameters"],
                "architecture": item["architecture"], "license": item["license"], "language_coverage": item["language_coverage"],
                "native_context_tokens": item["native_context_tokens"],
                "provenance_status": "original_historical_checkpoint_known;fixed_registry_bytes_verified;conversion_lineage_not_independently_reproduced",
                "tokenizer_status": "not_runtime_certified;conservative_budget_unless_verified_native_adapter_available",
                "license_action": "stored source license text; no gated login or new click-through acceptance performed"}}
    if item["id"] == "yi15-6b":
        model["suite_record"]["tokenizer_status"] = "official_HF_literal_backslash_template_differs_from_registry;runtime_uses_original_registry_ChatML_template;exact_tokenizer_equivalence_not_certified"
        model["suite_record"]["tokenizer_audit_artifact"] = "runtime/tokenizers/yi15-6b-771924d;reference_files_only_not_runtime_tokenizer_spec"
    return model


def assert_existing_identity(existing: dict, item: dict) -> None:
    if any(existing.get(key) != expected for key, expected in {
        "id": item["id"], "provider": "ollama", "model": item["model"],
        "base_url": BASE_URL, "expected_digest": item["digest"], "release_date": item["release_date"],
        "native_context_tokens": item["native_context_tokens"]}.items()):
        raise ValueError("Existing model ID has different configuration; never overwrite: " + item["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=BASE_URL)
    parser.add_argument("--only", nargs="+", choices=[item["id"] for item in SUITE])
    parser.add_argument("--output", type=Path, default=ROOT / "output/model-suite-20261024/installed.json")
    parser.add_argument("--freeze-tokenizer-only", action="store_true")
    parser.add_argument("--tokenizer-dest", type=Path, default=ROOT / "runtime/tokenizers/yi15-6b-771924d")
    args = parser.parse_args()
    if args.freeze_tokenizer_only:
        print(json.dumps({"tokenizer_spec": freeze_yi_tokenizer(args.tokenizer_dest), "downloaded_model_weights": False,
                          "native_adapter_runtime_certified": False}, ensure_ascii=False, indent=2))
        return
    assert_server_location(ROOT, sys.platform)
    if args.url != BASE_URL:
        parser.error("Only the project's isolated Ollama port 11435 is supported")
    sys.path.insert(0, str(ROOT))
    from backend import server
    selected = [item for item in SUITE if not args.only or item["id"] in args.only]
    ids = {item["id"] for item in selected}
    if any(r["status"] in {"running", "queued"} and ids.intersection(r["config"]["model_ids"]) for r in server.all_objects("run")):
        raise ValueError("Selected new model belongs to an active run; wait until idle")
    result = json.loads(args.output.read_bytes()) if args.output.exists() else {
        "client_date": "2026-10-24", "created_at_utc": now(), "models_directory": str(ROOT / "runtime/models"),
        "models": [], "errors": [], "installation_attempts": [],
        "policy": "historical original releases; fixed registry artifacts; private development only; no claim of zero contamination or reproduced conversion"}
    result["ollama_version"] = request_json(BASE_URL + "/api/version")
    for item in selected:
        event = {"model_id": item["id"], "started_at": now()}
        try:
            frozen = fixed_manifest(item)
            tags = {m["name"]: m for m in request_json(BASE_URL + "/api/tags")["models"]}
            if item["model"] not in tags:
                pull(BASE_URL, item["model"])
                tags = {m["name"]: m for m in request_json(BASE_URL + "/api/tags")["models"]}
            installed = tags[item["model"]]
            if installed["digest"] != item["digest"]:
                raise ValueError("Installed model tag digest differs from pre-download fixed identity")
            if installed.get("details", {}).get("quantization_level") != "Q4_K_M":
                raise ValueError("Expected Q4_K_M")
            verified = verify_blobs(ROOT / "runtime/models", item, frozen)
            details = request_json(BASE_URL + "/api/show", {"model": item["model"]}, timeout=60)
            model = new_model_record(item, server.now())
            existing = next((m for m in server.all_objects("model") if m["id"] == item["id"]), None)
            if existing:
                assert_existing_identity(existing, item)
                model = existing  # Explicitly keep existing registration; do not mutate completed snapshots/configs.
            else:
                server.put("model", item["id"], model)
            record = {"config": model, "tags": installed, "show": details, "verified_blobs": verified,
                      "template_sha256": hashlib.sha256(details.get("template", "").encode()).hexdigest(),
                      "parameters_sha256": hashlib.sha256(details.get("parameters", "").encode()).hexdigest(),
                      "full_model_blob_hash_verified": True, "installed_at_utc": now()}
            result["models"] = [m for m in result["models"] if m["config"]["id"] != item["id"]] + [record]
            result["errors"] = [e for e in result["errors"] if e["model_id"] != item["id"]]
            atomic_json(METADATA / (item["metadata_prefix"] + "-installed-show.json"), details)
            event.update(status="installed", digest=item["digest"], native_context_tokens=item["native_context_tokens"])
        except Exception as exc:
            event.update(status="failed", error=str(exc), type=type(exc).__name__)
            result["errors"] = [e for e in result["errors"] if e["model_id"] != item["id"]] + [dict(event)]
        event["finished_at"] = now()
        result["installation_attempts"].append(event)
        result["updated_at_utc"] = now()
        atomic_json(args.output, result)
        print(json.dumps(event, ensure_ascii=False), flush=True)
    if any(e["model_id"] in ids for e in result["errors"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
