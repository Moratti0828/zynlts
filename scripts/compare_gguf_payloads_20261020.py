"""Read-only GGUF v3 metadata/tensor comparison; no model loading or downloads.

Run on the host containing both full files. Each full file is scanned once after
its small GGUF directory is parsed. Tensor hashes exclude alignment padding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO


SCALARS = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
# ggml type -> (elements per block, bytes per block). Unknown types fail closed.
TYPES = {
    0: (1, 4), 1: (1, 2), 2: (32, 18), 3: (32, 20),
    6: (32, 22), 7: (32, 24), 8: (32, 34), 9: (32, 40),
    10: (256, 84), 11: (256, 110), 12: (256, 144),
    13: (256, 176), 14: (256, 210), 15: (256, 292),
    24: (1, 1), 25: (1, 2), 26: (1, 4), 27: (1, 8),
    28: (1, 8), 30: (1, 2),
}
TYPE_NAMES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64", 30: "BF16"}


def read_exact(handle: BinaryIO, size: int) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise ValueError(f"Unexpected EOF at {handle.tell()}, wanted {size} bytes")
    return data


def unpack(handle: BinaryIO, fmt: str) -> Any:
    return struct.unpack("<" + fmt, read_exact(handle, struct.calcsize("<" + fmt)))[0]


def read_string(handle: BinaryIO) -> str:
    size = unpack(handle, "Q")
    if size > 64 * 1024 * 1024:
        raise ValueError(f"Unreasonable GGUF string size: {size}")
    return read_exact(handle, size).decode("utf-8", errors="strict")


def read_value(handle: BinaryIO, kind: int, depth: int = 0) -> Any:
    if depth > 4:
        raise ValueError("Excessively nested GGUF metadata array")
    if kind in SCALARS:
        return unpack(handle, SCALARS[kind])
    if kind == 8:
        return read_string(handle)
    if kind == 9:
        element_type, count = unpack(handle, "I"), unpack(handle, "Q")
        if count > 2_000_000:
            raise ValueError(f"Unreasonable GGUF array size: {count}")
        return {"element_type": element_type, "values": [read_value(handle, element_type, depth + 1) for _ in range(count)]}
    raise ValueError(f"Unknown GGUF metadata type {kind}")


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def describe_value(value: Any) -> Any:
    if isinstance(value, dict) and "values" in value:
        return {"element_type": value["element_type"], "count": len(value["values"]), "canonical_value_sha256": canonical_hash(value), "preview": value["values"][:3]}
    return value


def parse_directory(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        if read_exact(handle, 4) != b"GGUF":
            raise ValueError("Not a little-endian GGUF file")
        version = unpack(handle, "I")
        if version != 3:
            raise ValueError(f"Only GGUF v3 is supported, found {version}")
        tensor_count, metadata_count = unpack(handle, "Q"), unpack(handle, "Q")
        if tensor_count > 100_000 or metadata_count > 100_000:
            raise ValueError("Unreasonable GGUF directory size")
        metadata: dict[str, Any] = {}
        for _ in range(metadata_count):
            key, kind = read_string(handle), unpack(handle, "I")
            if key in metadata:
                raise ValueError(f"Duplicate metadata key {key}")
            value = read_value(handle, kind)
            metadata[key] = {"gguf_type": kind, "canonical_value_sha256": canonical_hash(value), "value": describe_value(value)}
        tensors = []
        names: set[str] = set()
        for _ in range(tensor_count):
            name, dimension_count = read_string(handle), unpack(handle, "I")
            if name in names or not 1 <= dimension_count <= 4:
                raise ValueError(f"Invalid tensor directory entry {name}")
            names.add(name)
            dimensions = [unpack(handle, "Q") for _ in range(dimension_count)]
            kind, offset = unpack(handle, "I"), unpack(handle, "Q")
            if kind not in TYPES:
                raise ValueError(f"Unsupported ggml type {kind} for {name}")
            block, block_bytes = TYPES[kind]
            elements = math.prod(dimensions)
            if not all(dimensions) or dimensions[0] % block or elements % block:
                raise ValueError(f"Invalid block layout for {name}")
            tensors.append({"name": name, "dimensions": dimensions, "ggml_type": kind, "ggml_type_name": TYPE_NAMES[kind], "offset": offset, "element_count": elements, "payload_bytes": elements // block * block_bytes})
        alignment = metadata.get("general.alignment", {}).get("value", 32)
        if not isinstance(alignment, int) or alignment <= 0 or alignment & (alignment - 1):
            raise ValueError(f"Invalid alignment {alignment}")
        directory_end = handle.tell()
        data_offset = (directory_end + alignment - 1) // alignment * alignment
    return {"path": str(path), "file_bytes": path.stat().st_size, "gguf_version": version, "metadata_count": metadata_count, "tensor_count": tensor_count, "alignment": alignment, "directory_end": directory_end, "data_offset": data_offset, "metadata": metadata, "tensors": tensors}


def scan_file(directory: dict[str, Any], expected_sha256: str) -> dict[str, Any]:
    whole = hashlib.sha256()
    aggregate = hashlib.sha256()
    data_section = hashlib.sha256()
    data_offset = directory["data_offset"]
    position = 0

    def consume(handle: BinaryIO, length: int, tensor_digest: Any = None) -> None:
        nonlocal position
        if length < 0:
            raise ValueError("Overlapping or out-of-order tensor payloads")
        while length:
            chunk = read_exact(handle, min(length, 8 * 1024 * 1024))
            whole.update(chunk)
            if position >= data_offset:
                data_section.update(chunk)
            elif position + len(chunk) > data_offset:
                data_section.update(chunk[data_offset - position:])
            if tensor_digest is not None:
                tensor_digest.update(chunk)
                aggregate.update(chunk)
            position += len(chunk)
            length -= len(chunk)

    with Path(directory["path"]).open("rb") as handle:
        consume(handle, data_offset)
        for tensor in sorted(directory["tensors"], key=lambda row: row["offset"]):
            absolute = data_offset + tensor["offset"]
            if tensor["offset"] % directory["alignment"]:
                raise ValueError(f"Unaligned tensor {tensor['name']}")
            consume(handle, absolute - position)
            digest = hashlib.sha256()
            consume(handle, tensor["payload_bytes"], digest)
            tensor["payload_sha256"] = digest.hexdigest()
        consume(handle, directory["file_bytes"] - position)
        if handle.read(1):
            raise ValueError("File changed size during scan")
    directory.update({"file_sha256": whole.hexdigest(), "expected_file_sha256": expected_sha256, "file_sha256_matches_expected": whole.hexdigest() == expected_sha256, "tensor_payload_bytes": sum(t["payload_bytes"] for t in directory["tensors"]), "tensor_payload_concat_sha256": aggregate.hexdigest(), "data_section_sha256": data_section.hexdigest()})
    return directory


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    metadata_differences = []
    for key in sorted(set(left["metadata"]) | set(right["metadata"])):
        l_value, r_value = left["metadata"].get(key), right["metadata"].get(key)
        if l_value != r_value:
            metadata_differences.append({"key": key, "left": l_value, "right": r_value, "tokenizer_or_chat_template": key.startswith("tokenizer.") or "chat_template" in key})
    left_tensors = {item["name"]: item for item in left["tensors"]}
    right_tensors = {item["name"]: item for item in right["tensors"]}
    differences = []
    layout_differences = []
    payload_differences = []
    for name in sorted(set(left_tensors) | set(right_tensors)):
        l_value, r_value = left_tensors.get(name), right_tensors.get(name)
        if l_value != r_value:
            differences.append({"name": name, "left": l_value, "right": r_value})
        l_layout = {key: value for key, value in (l_value or {}).items() if key != "payload_sha256"}
        r_layout = {key: value for key, value in (r_value or {}).items() if key != "payload_sha256"}
        if l_layout != r_layout:
            layout_differences.append(name)
        if l_value is None or r_value is None or l_value.get("payload_sha256") != r_value.get("payload_sha256"):
            payload_differences.append(name)
    valid_sha = left["file_sha256_matches_expected"] and right["file_sha256_matches_expected"]
    equal = not differences and left["tensor_payload_concat_sha256"] == right["tensor_payload_concat_sha256"]
    return {"both_expected_full_file_hashes_verified": valid_sha, "tensor_directory_and_each_payload_identical": equal, "tensor_layout_identical": not layout_differences, "tensor_layout_difference_names": layout_differences, "tensor_payload_difference_count": len(payload_differences), "tensor_payload_difference_names": payload_differences, "tensor_difference_count": len(differences), "tensor_differences": differences, "metadata_difference_count": len(metadata_differences), "metadata_differences": metadata_differences, "tokenizer_or_chat_template_differences": [item for item in metadata_differences if item["tokenizer_or_chat_template"]], "data_sections_identical_including_padding": left["data_section_sha256"] == right["data_section_sha256"], "certified_quantized_tensor_content_equivalent": bool(valid_sha and equal), "interpretation": "Tensor-content equivalence only; this does not certify training cutoff, corpus absence, prompt-template equivalence, or human annotation."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--left-sha256", required=True)
    parser.add_argument("--right-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {args.left.resolve(), args.right.resolve()}:
        parser.error("Output cannot replace a source GGUF")
    left = scan_file(parse_directory(args.left), args.left_sha256)
    right = scan_file(parse_directory(args.right), args.right_sha256)
    result = {"schema": "gguf-readonly-payload-provenance-v1", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "method": "Python stdlib GGUF v3 parse; independent whole-file and per-tensor SHA-256; no model execution; payload hashes exclude padding", "left": left, "right": right, "comparison": compare(left, right)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_keys = ("both_expected_full_file_hashes_verified", "tensor_directory_and_each_payload_identical", "tensor_difference_count", "metadata_difference_count", "certified_quantized_tensor_content_equivalent")
    print(json.dumps({"output": str(args.output), **{key: result["comparison"][key] for key in summary_keys}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
