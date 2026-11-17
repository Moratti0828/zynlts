"""Run the fixed Qwen7B same-protocol anchor after the finite tail completes."""
import subprocess
import sys
from scripts.run_expansion_tail_20261025 import OUT, ROOT, wait_for


if __name__ == "__main__":
    for stage in ("bridge", "reference", "yi", "recent"):
        wait_for(OUT / (stage + "-status.json"), lambda value: value.get("complete") is True)
    subprocess.run([sys.executable, "-u", "-m", "scripts.run_expansion_20261024", "--stage", "anchor"], cwd=ROOT, check=True)
