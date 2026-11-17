"""Create a server-local Compose .env without displaying the access token."""

import argparse
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name(".env"))
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        raise SystemExit(f"Environment file already exists; preserved: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join([
        "# Generated locally. Keep this file private.",
        f"READING_BENCH_TOKEN={secrets.token_urlsafe(32)}",
        "APP_HOST_BIND=127.0.0.1",
        "APP_PORT=8787",
        "READING_BENCH_OLLAMA_URL=http://ollama:11434",
        "PYTHON_IMAGE=python:3.11-slim",
        "OLLAMA_IMAGE=ollama/ollama:latest",
        "",
    ])
    # O_EXCL avoids overwriting an environment file created concurrently.
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)
    print(f"Created private environment file: {target}")
    print("Read the token locally when entering the platform; do not paste it into chat.")


if __name__ == "__main__":
    main()
