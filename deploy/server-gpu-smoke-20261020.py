"""One short engineering inference; preserves unmodified response and GPU proof."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

payload = {
    "model": "qwen2.5:7b-instruct",
    "prompt": "阅读短文，然后只输出答案数字。短文：研究小组先采集了12份样本，随后又补充了8份。问题：一共采集多少份样本？",
    "stream": False,
    "keep_alive": "10m",
    "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 64},
}
record = {"recorded_at_server_utc": datetime.now(timezone.utc).isoformat(), "purpose": "engineering GPU smoke, not benchmark score", "request": payload}
started = time.monotonic()
try:
    with urlopen(Request("http://127.0.0.1:11435/api/generate", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}), timeout=120) as response:
        record["response"] = json.load(response)
    record["elapsed_seconds"] = time.monotonic() - started
    with urlopen("http://127.0.0.1:11435/api/ps", timeout=10) as response:
        record["loaded_models"] = json.load(response)
except (OSError, ValueError) as exc:
    record["error"] = str(exc)
    record["elapsed_seconds"] = time.monotonic() - started
for label, argv in {
    "gpu": ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.free,utilization.gpu", "--format=csv"],
    "processes": ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory", "--format=csv"],
}.items():
    result = subprocess.run(argv, text=True, capture_output=True, timeout=20)
    record[label] = {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
rendered = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
Path("output/server-gpu-smoke-20261020.json").write_text(rendered, encoding="utf-8")
print(rendered, end="")
