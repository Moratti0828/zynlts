"""Archive only a rejected, never-created public-reference job, then retry."""
import json
from pathlib import Path
import shutil
import sys
from backend import server

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    folder = ROOT / "output/expansion-20261024/reference-squad2"
    archive = ROOT / "output/reference-admission-rejection-20261025"
    archive.mkdir(exist_ok=True)
    if folder.exists():
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["specification"]["bank"] == "reference-squad2-20261024"
        assert all(not job.get("run_id") and job["status"] in {"rejected", "planned"} for job in manifest["jobs"])
        assert not any(r["config"].get("bank_id") == "reference-squad2-20261024" for r in server.all_objects("run"))
        target = archive / "reference-squad2"
        assert folder.resolve().is_relative_to((ROOT / "output").resolve())
        assert target.resolve().is_relative_to((ROOT / "output").resolve()) and not target.exists()
        shutil.move(str(folder), str(target))
    initial = ROOT / "data/reference/initial-import-banks-20261024"
    initial.mkdir(exist_ok=True)
    for dataset in ("squad2", "cmrc2018"):
        path = ROOT / f"data/annotation/reference-{dataset}-20261024.json"
        if path.exists():
            target = initial / path.name
            assert path.resolve().is_relative_to((ROOT / "data/annotation").resolve()) and not target.exists()
            shutil.move(str(path), str(target))
    print(json.dumps({"admission_rejected_no_inference": True, "archive": str(archive)}))


if __name__ == "__main__":
    main()
