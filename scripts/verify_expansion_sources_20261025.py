"""Read-only evidence availability checks; no downloads or model calls."""
import hashlib
import json
from pathlib import Path
from scripts.import_public_reference_20261024 import SOURCES, SOURCE_DIR

ROOT = Path(__file__).resolve().parents[1]


def main():
    bank = json.loads((ROOT / "data/annotation/dev-recent-additions-20261024.json").read_text(encoding="utf-8"))
    missing, verified = [], []
    for article in bank["articles"]:
        for field, gold in (("source_raw_path", "source_raw_sha256"), ("source_text_path", "source_text_sha256")):
            path = (ROOT / article[field]).resolve()
            assert path.is_relative_to((ROOT / "data/candidates").resolve())
            if not path.is_file():
                missing.append(article[field])
                continue
            raw = path.read_bytes() if field == "source_raw_path" else path.read_text(encoding="utf-8").strip().encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != article[gold]:
                raise ValueError("Source bytes disagree with frozen article: " + str(path))
            verified.append(article[field])
    for source in SOURCES:
        path = SOURCE_DIR / source["filename"]
        if not path.is_file():
            missing.append(path.relative_to(ROOT).as_posix())
        elif hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Public reference source hash changed: " + source["filename"])
        else:
            verified.append(path.relative_to(ROOT).as_posix())
    result = {"verified_source_files": len(verified), "missing_paths": missing, "all_available_and_hash_matched": not missing, "model_calls": 0}
    (ROOT / "output/expansion-source-availability-20261025.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
