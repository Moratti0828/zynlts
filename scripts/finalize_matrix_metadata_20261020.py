"""Idle-only project metadata/backup capture, without changing sealed runs."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main() -> None:
    from backend import server
    active = [r["id"] for r in server.all_objects("run") if r["status"] in {"running", "queued"}]
    if active:
        raise RuntimeError("Active runs retained; finalize after they complete: " + ",".join(active))
    model = server.get("model", "internlm25-7b")
    model["name"] = "InternLM2.5 · 7B Chat（registry分发待核）"
    model["provenance_review"] = {"client_date": "2026-10-20", "status": "not_equivalent_to_official_2024_gguf;historical_conversion_lineage_unverified", "different_quantized_tensors": 226, "different_tokenizer_metadata_entries": 3, "not_a_retraining_or_contamination_proof": True, "separate_official_configuration": "internlm25-7b-official2024"}
    server.put("model", model["id"], model)
    target = ROOT / "runtime/deployments/20261020/bench-final.sqlite3"
    if target.exists():
        raise FileExistsError("Preserve existing final backup; choose a distinct name")
    with sqlite3.connect(str(server.DB)) as source, sqlite3.connect(str(target)) as destination:
        source.backup(destination)
    records = {"created_at": server.now(), "backup": str(target), "health_version": server.APP_VERSION, "models": [server.model_status(m) for m in server.all_objects("model")], "run_ids": [{"id": r["id"], "status": r["status"], "progress": r["progress"], "bank_id": r["config"].get("bank_id"), "formal": r.get("formal"), "errors": sum(bool(x.get("error")) for x in r.get("results", []))} for r in server.all_objects("run") if r.get("created_at", "").startswith("2026-10-20")]}
    (ROOT / "output/final-platform-state-20261020.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"backup": str(target), "models": len(records["models"]), "completed_run_count": len(records["run_ids"])}))

if __name__ == "__main__":
    main()
