"""Reading Bench: reproducible, local-first reading evaluation."""
import sys

if sys.version_info < (3, 11):
    raise RuntimeError("Reading Bench requires Python 3.11 or newer; run with python3.12 or a Python 3.11+ virtual environment.")
