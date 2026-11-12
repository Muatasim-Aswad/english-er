#!/usr/bin/env python3
"""Smoke-test the built UI and API from one isolated loopback origin."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = 8765


def _get(path: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=2) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="english-er-production-") as temporary:
        root = Path(temporary)
        data_home = root / "data"
        state_home = root / "state"
        database = data_home / "english-er" / "english-er.sqlite3"
        database.parent.mkdir(mode=0o700, parents=True)
        environment = os.environ.copy()
        environment.update(
            {
                "ENGLISH_ER_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
                "XDG_DATA_HOME": str(data_home),
                "XDG_STATE_HOME": str(state_home),
            }
        )
        subprocess.run(
            [
                "uv",
                "run",
                "--offline",
                "--frozen",
                "--directory",
                str(repository_root / "apps" / "backend"),
                "alembic",
                "upgrade",
                "head",
            ],
            check=True,
            env=environment,
            stdout=subprocess.DEVNULL,
        )
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "--offline",
                "--frozen",
                "--directory",
                str(repository_root / "apps" / "backend"),
                "uvicorn",
                "english_er.entrypoints.http:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(PORT),
                "--no-access-log",
                "--log-level",
                "warning",
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    stderr = (
                        process.stderr.read().decode(errors="replace") if process.stderr else ""
                    )
                    raise RuntimeError(f"production server exited early: {stderr[-1000:]}")
                try:
                    status, health_body = _get("/api/v1/health")
                except OSError:
                    status = 0
                    health_body = b""
                if status == 200:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("production server did not become ready")
                time.sleep(0.1)

            health = json.loads(health_body)
            if health != {"api": "ok", "database": "ok"}:
                raise RuntimeError("health response did not report API and database readiness")
            index_status, index = _get("/")
            if index_status != 200 or b'<div id="root"></div>' not in index:
                raise RuntimeError("production UI index was not served")
            asset_match = re.search(rb'(?:src|href)="(/assets/[^"]+)"', index)
            if asset_match is None or _get(asset_match.group(1).decode())[0] != 200:
                raise RuntimeError("production UI asset was not served from the API origin")
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/version.json", timeout=2) as response:
                expected = json.loads((repository_root / "apps/web/dist/version.json").read_text())
                if response.headers.get("Cache-Control") != "no-store" or json.load(response) != expected:
                    raise RuntimeError("production build identity was stale or cacheable")
            if _get("/api/v1/not-a-route")[0] != 404:
                raise RuntimeError("unknown /api/v1 route was intercepted by the SPA fallback")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        if state_home.exists() and (state_home / "english-er" / "capture-enabled").exists():
            raise RuntimeError("production smoke enabled capture")
    print(f"Production UI/API smoke passed on 127.0.0.1:{PORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
