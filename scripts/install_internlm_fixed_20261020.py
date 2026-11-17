"""Import the official 2024 InternLM GGUF after SHA256 validation.

Uses an explicit immutable HF mirror URL when the server cannot reach HF.
All weights, partial downloads, licenses and manifests stay in this project.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SHA = "450ef0b157ee10586bb8fce4c5173ae1799345c43c537a6a7353518df1079f55"
REV = "8fa9dff166b63e3d356b3a3ca95c5ab2a4b1b378"
SIZE = 4712768320
NAME = "reading-internlm25-7b:20240716-q4_K_M"
URL = f"https://hf-mirror.com/internlm/internlm2_5-7b-chat-gguf/resolve/{REV}/internlm2_5-7b-chat-q4_k_m.gguf"

def request(path: str, body: dict | None = None) -> dict:
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request("http://127.0.0.1:11435" + path, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)

def file_sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def download_fixed(target: Path) -> None:
    """Resume byte-range chunks, then require the official whole-file digest."""
    chunks = ROOT / "runtime" / "models" / "internlm-fixed-download-chunks"
    chunks.mkdir(exist_ok=True)
    chunk_size = 32 * 1024 * 1024
    partial = target.with_suffix(".fixed-download.part")
    # The previous sequential transfer is a valid prefix; reuse complete chunks
    # after that explicitly owned transfer has been stopped by the operator.
    if partial.exists():
        with partial.open("rb") as source:
            for index in range(min(partial.stat().st_size, SIZE) // chunk_size):
                chunk = chunks / f"{index:04d}.bin"
                data = source.read(chunk_size)
                if not chunk.exists():
                    chunk.write_bytes(data)
    def get(index: int) -> Path:
        start, end = index * chunk_size, min(SIZE, (index + 1) * chunk_size) - 1
        expected = end - start + 1
        destination = chunks / f"{index:04d}.bin"
        if destination.exists() and destination.stat().st_size == expected:
            return destination
        last_error = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(req, timeout=120) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{SIZE}":
                        raise ValueError("Mirror did not honor the exact byte range")
                    temporary = destination.with_suffix(".tmp")
                    count = 0
                    with temporary.open("wb") as output:
                        while block := response.read(1024 * 1024):
                            count += len(block)
                            if count > expected:
                                raise ValueError("Range response too large")
                            output.write(block)
                    if count != expected:
                        raise ValueError("Incomplete byte-range response")
                    temporary.replace(destination)
                print(json.dumps({"download_chunk": index, "bytes": expected}), flush=True)
                return destination
            except Exception as exc:
                last_error = exc
                time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"Chunk {index} failed: {last_error}")
    count = (SIZE + chunk_size - 1) // chunk_size
    with ThreadPoolExecutor(max_workers=8) as pool:
        ordered = list(pool.map(get, range(count)))
    assembled = target.with_suffix(".assembled.part")
    with assembled.open("wb") as output:
        for chunk in ordered:
            with chunk.open("rb") as source:
                while block := source.read(8 * 1024 * 1024):
                    output.write(block)
    if assembled.stat().st_size != SIZE or file_sha(assembled) != SHA:
        raise ValueError("Fixed official GGUF size/SHA256 mismatch; parts retained, no import")
    assembled.replace(target)

def main() -> None:
    from backend import server
    target = ROOT / "runtime" / "models" / "blobs" / ("sha256-" + SHA)
    evidence = ROOT / "output" / "model-suite-20261020"
    evidence.mkdir(exist_ok=True)
    if not target.exists():
        download_fixed(target)
    if target.stat().st_size != SIZE or file_sha(target) != SHA:
        raise ValueError("Existing official blob size/hash mismatch")
    template = (evidence / "internlm-native-template.txt").read_text(encoding="utf-8")
    expected_template = "62fbfd9ed093d6e5ac83190c86eec5369317919f4b149598d2dbb38900e9faef"
    if hashlib.sha256(template.encode()).hexdigest() != expected_template:
        raise ValueError("Frozen InternLM runtime template mismatch")
    modelfile = evidence / "InternLM.Modelfile"
    modelfile.write_text(f'FROM {target}\nTEMPLATE """{template}"""\nPARAMETER stop "<|im_end|>"\nPARAMETER stop "</s>"\n', encoding="utf-8")
    subprocess.run(["/usr/local/bin/ollama", "create", NAME, "-f", str(modelfile)], env={**os.environ, "OLLAMA_HOST": "127.0.0.1:11435"}, check=True)
    installed = next(m for m in request("/api/tags")["models"] if m["name"] == NAME)
    details = request("/api/show", {"model": NAME})
    if details.get("details", {}).get("quantization_level") != "Q4_K_M":
        raise ValueError("Imported quantization mismatch")
    manifest_path = ROOT / "runtime/models/manifests/registry.ollama.ai/library/reading-internlm25-7b/20240716-q4_K_M"
    manifest = json.loads(manifest_path.read_bytes())
    weight = next(x for x in manifest["layers"] if x["mediaType"] == "application/vnd.ollama.image.model")
    if weight["digest"] != "sha256:" + SHA:
        raise ValueError("Imported weight layer differs from official frozen blob")
    config = {"id": "internlm25-7b-official2024", "name": "InternLM2.5 · 7B Chat（官方2024 GGUF）", "provider": "ollama", "base_url": "http://127.0.0.1:11435", "model": NAME, "expected_digest": installed["digest"], "api_key_env": "", "release_date": "2024-07-16", "release_source": "https://huggingface.co/internlm/internlm2_5-7b-chat-gguf/tree/" + REV, "created_at": server.now(), "suite_record": {"official_gguf_repo": "internlm/internlm2_5-7b-chat-gguf", "gguf_revision": REV, "original_model_release_date": "2024-07-03", "historical_revision_date": "2024-07-16", "official_weight_blob_sha256": SHA, "distribution_manifest_sha256": installed["digest"], "conversion_lineage": "official author's 2024 GGUF bytes verified; original tensor-to-GGUF transformation not independently repeated", "runtime_template_status": "frozen InternLM ChatML runtime template; exact tokenizer accounting not certified; engine BOS behavior retained"}}
    server.put("model", config["id"], config)
    result = {"recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "config": config, "tags": installed, "show": details, "source_download_url": URL, "weight_bytes": SIZE, "verified_weight_sha256": SHA, "model_directory": str(target.parent), "license_note": "Official GGUF card metadata says Apache2.0; original model-card weight terms also retained for academic evaluation; do not assume code license overrides weights."}
    (evidence / "internlm-fixed-installed.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"installed": config["id"], "digest": installed["digest"], "weight_sha256_verified": SHA}), flush=True)

if __name__ == "__main__":
    main()
