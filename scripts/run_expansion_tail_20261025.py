"""Finish the predeclared finite stages after the existing bridge controller."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/expansion-20261024"


def wait_for(path: Path, predicate) -> dict:
    deadline = time.monotonic() + 21600
    while time.monotonic() < deadline:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            if predicate(value):
                return value
        time.sleep(15)
    raise RuntimeError("Finite stage wait expired; no unconfirmed work was started: " + str(path))


def main() -> None:
    wait_for(OUT / "bridge-status.json", lambda value: value.get("complete") is True)
    for stage in ("reference", "yi", "recent"):
        if stage == "recent":
            # This marker is written by the parent only after independent AI
            # content review and any pre-run gold fixes; human review stays 0.
            wait_for(ROOT / "runtime/deployments/20261024/recent-reviewed.json", lambda value: value.get("ready") is True)
        result = subprocess.run([sys.executable, "-u", "-m", "scripts.run_expansion_20261024", "--stage", stage], cwd=ROOT)
        if result.returncode != 0:
            raise RuntimeError("Stage controller stopped; review its preserved manifest: " + stage)
    print(json.dumps({"complete": True, "stages": ["bridge", "reference", "yi", "recent"]}), flush=True)


if __name__ == "__main__":
    main()
