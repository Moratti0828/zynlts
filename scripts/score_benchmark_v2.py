#!/usr/bin/env python3
"""Score v2 planned bank and externally captured model responses; no inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.benchmark_v2 import evaluate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bank", required=True, type=Path)
    p.add_argument("--responses", required=True, type=Path)
    p.add_argument("--model-ids", required=True, nargs="+")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--allow-draft", action="store_true", help="Label output as diagnostic, never formal")
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    bank_raw, responses_raw = args.bank.read_bytes(), args.responses.read_bytes()
    report = evaluate(json.loads(bank_raw), json.loads(responses_raw), args.model_ids, args.allow_draft, args.bootstrap, args.seed)
    report["inputs"] = {"bank_sha256": hashlib.sha256(bank_raw).hexdigest(), "responses_sha256": hashlib.sha256(responses_raw).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"formal": report["formal"], "models": len(args.model_ids), "planned_response_rows": len(report["rows"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
