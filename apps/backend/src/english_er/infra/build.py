"""Resolve installed product identity and clean source build metadata."""

import json
import os
import subprocess
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict

VERSION = version("english-er-backend")
SOURCE_ROOT = Path(__file__).resolve().parents[5]


class BuildInfo(TypedDict):
    version: str
    revision: str
    commit_time: str | None
    build_time: str


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], stderr=subprocess.DEVNULL, text=True
    ).strip()


def source_build(root: Path = SOURCE_ROOT) -> BuildInfo:
    revision = "dev"
    commit_time = None
    try:
        if (root / ".git").exists() and not _git(
            root, "status", "--porcelain", "--untracked-files=normal"
        ):
            revision = _git(root, "rev-parse", "HEAD")
            commit_time = _git(root, "show", "-s", "--format=%cI", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        pass
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    build_time = (
        datetime.fromtimestamp(int(epoch), UTC).isoformat()
        if epoch is not None
        else commit_time or datetime.now(UTC).isoformat()
    )
    return {
        "version": VERSION,
        "revision": revision,
        "commit_time": commit_time,
        "build_time": build_time,
    }


def served_build(web_root: Path) -> BuildInfo:
    path = web_root / "version.json"
    if not path.is_file():
        return source_build()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or set(payload) != {"version", "revision", "commit_time", "build_time"}
        or not all(isinstance(payload[key], str) for key in ("version", "revision", "build_time"))
        or not (payload["commit_time"] is None or isinstance(payload["commit_time"], str))
    ):
        raise ValueError("Invalid frontend build identity; rebuild the frontend")
    return BuildInfo(
        version=payload["version"],
        revision=payload["revision"],
        commit_time=payload["commit_time"],
        build_time=payload["build_time"],
    )


if __name__ == "__main__":
    print(json.dumps(source_build(), sort_keys=True))
