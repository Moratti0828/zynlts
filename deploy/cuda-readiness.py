import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser(description='Initialize the CUDA driver in a fresh, explicitly selected process; does not allocate model weights.')
parser.add_argument('--device', default='0')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
os.environ['CUDA_VISIBLE_DEVICES'] = args.device
record = {'recorded_at_server_utc': datetime.now(timezone.utc).isoformat(),
          'cuda_visible_devices': args.device, 'library': 'libcuda.so.1', 'cuda_available': False}
try:
    driver = ctypes.CDLL('libcuda.so.1')
    init_code = driver.cuInit(0)
    record['cuInit_code'] = init_code
    count = ctypes.c_int()
    count_code = driver.cuDeviceGetCount(ctypes.byref(count))
    record['cuDeviceGetCount_code'] = count_code
    record['device_count'] = count.value
    record['cuda_available'] = init_code == 0 and count_code == 0 and count.value > 0
    if init_code != 0:
        error_name = ctypes.c_char_p()
        driver.cuGetErrorName(init_code, ctypes.byref(error_name))
        record['cuda_error_name'] = error_name.value.decode() if error_name.value else 'unknown'
except OSError as exc:
    record['load_error'] = str(exc)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
raise SystemExit(0 if record['cuda_available'] else 5)
