#!/usr/bin/env python3
"""Run the explicit migration and ordered user-service restarts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _required_executable(environment_name: str, default: str) -> str:
    configured = os.environ.get(environment_name)
    if configured:
        return configured
    resolved = shutil.which(default)
    if resolved is None:
        raise SystemExit(f"{default} is required")
    return resolved


def _database_url() -> str:
    configured = os.environ.get("ENGLISH_ER_DATABASE_URL")
    if configured:
        return configured
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    database = base / "english-er" / "english-er.sqlite3"
    database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    database.parent.chmod(0o700)
    return f"sqlite+aiosqlite:///{database.resolve()}"


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    uv = _required_executable("ENGLISH_ER_UV", "uv")
    systemctl = _required_executable("ENGLISH_ER_SYSTEMCTL", "systemctl")
    environment = os.environ.copy()
    environment["ENGLISH_ER_DATABASE_URL"] = _database_url()

    migration = [
        uv,
        "run",
        "--offline",
        "--frozen",
        "--directory",
        str(repository_root / "apps" / "backend"),
        "alembic",
        "upgrade",
        "head",
    ]
    try:
        subprocess.run(migration, check=True, env=environment)
        subprocess.run([systemctl, "--user", "restart", "english-er-api.service"], check=True)
        subprocess.run([systemctl, "--user", "restart", "english-er-worker.service"], check=True)
    except subprocess.CalledProcessError as error:
        print(f"local deploy stopped: command failed with exit {error.returncode}", file=sys.stderr)
        return error.returncode
    print("Local deploy completed: migration, API restart, worker restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
