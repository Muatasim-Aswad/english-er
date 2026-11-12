#!/usr/bin/env python3
"""Reject stale frontend builds and verify the running local revision."""

import argparse
import json
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require_identity(actual: object, expected: dict[str, str]) -> None:
    if not isinstance(actual, dict) or any(
        actual.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(
            "Build identity differs; build from the clean intended commit before deployment"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--running", action="store_true")
    args = parser.parse_args()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True):
        raise SystemExit("Deployment requires clean tracked and untracked source")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    version = tomllib.loads((ROOT / "apps/backend/pyproject.toml").read_text())["project"][
        "version"
    ]
    expected = {"revision": revision, "version": version}
    if not args.running:
        require_identity(json.loads((ROOT / "apps/web/dist/version.json").read_text()), expected)
        print(f"PASS frontend build {version} at {revision}")
        return
    deadline = time.monotonic() + 20
    while True:
        try:
            request = urllib.request.Request(
                "http://127.0.0.1:8001/version.json", headers={"Cache-Control": "no-cache"}
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                require_identity(json.load(response), expected)
            print(f"PASS running build {version} at {revision}")
            return
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise SystemExit("Running API did not serve the intended build revision") from None
            time.sleep(0.2)


if __name__ == "__main__":
    main()
