#!/usr/bin/env python3
"""Voxtype post-process hook: atomically spool text and echo stdin exactly."""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

DIRECTORY_MODE = 0o700
FILE_MODE = 0o600


def _state_root() -> Path:
    override = os.environ.get("ENGLISH_ER_STATE_ROOT")
    if override:
        return Path(override)
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "english-er"
    return Path.home() / ".local" / "state" / "english-er"


def _uuid7(timestamp_ms: int) -> uuid.UUID:
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (
        ((timestamp_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (random_a << 64)
        | (0b10 << 62)
        | random_b
    )
    return uuid.UUID(int=value)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_directory(path: Path) -> None:
    path.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
    path.chmod(DIRECTORY_MODE)


def _capture(raw: bytes, state_root: Path) -> None:
    if not (state_root / "capture-enabled").is_file():
        return

    text = raw.decode("utf-8", errors="strict")
    spool = state_root / "spool"
    pending = spool / "pending"
    for directory in (state_root, spool, pending, spool / "processing", spool / "failed"):
        _ensure_directory(directory)

    timestamp_ns = time.time_ns()
    capture_id = _uuid7(timestamp_ns // 1_000_000)
    captured_at = datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=UTC)
    envelope = {
        "version": 1,
        "id": str(capture_id),
        "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
        "source": "voxtype",
        "text": text,
    }
    encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    temporary = pending / f".{capture_id}.tmp"
    final = pending / f"{capture_id}.json"
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, final)
        _fsync_directory(pending)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        _capture(raw, _state_root())
    except BaseException as error:
        print(f"english-er capture failed: {type(error).__name__}", file=sys.stderr)
    try:
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
