"""Read-only, relocatable verification of the completed expansion delivery."""
import hashlib
import json
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relocated(value):
    # The source manifest preserves the original local capture paths. Retain
    # that provenance while checking the identical files in this checkout.
    parts = PureWindowsPath(value).parts if "\\" in value else Path(value).parts
    if "reading-bench" in parts:
        parts = parts[parts.index("reading-bench") + 1:]
    candidate = ROOT.joinpath(*parts).resolve()
    candidate.relative_to(ROOT.resolve())
    return candidate


def main():
    delivery = load(ROOT / "output/delivery-expansion-20261025.json")
    checked = set()

    def check(path, expected):
        if digest(path) != expected:
            raise ValueError("SHA256 mismatch: " + str(path))
        checked.add(path)

    for name in ("report", "analysis_bundle"):
        item = delivery[name]
        check(relocated(item["path"]), item["sha256"])
    check(ROOT / "output/final-platform-state-20261025.json", delivery["final_platform_state_sha256"])
    for item in delivery["source_artifacts"] + delivery["supporting_artifacts"]:
        check(relocated(item["path"]), item["sha256"])
    bundle_path = relocated(delivery["analysis_bundle"]["path"])
    manifest = load(bundle_path)
    if not manifest["complete_inputs"] or manifest["counts"] != delivery["expansion_counts"]:
        raise ValueError("Delivery count/completion mismatch")
    for item in manifest["outputs"]:
        path = (bundle_path.parent / item["path"]).resolve()
        path.relative_to(bundle_path.parent.resolve())
        check(path, item["sha256"])
    if len(delivery["jobs"]) != 23 or not all(job["gpu_observed"] for job in delivery["jobs"]):
        raise ValueError("Incomplete job or device evidence")
    print(json.dumps({"status": "ok", "verified_unique_files": len(checked),
                      "counts": delivery["expansion_counts"], "model_calls": 0}))


if __name__ == "__main__":
    main()
