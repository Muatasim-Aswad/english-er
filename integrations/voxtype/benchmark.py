#!/usr/bin/env python3
"""Dependency-free warmed latency gate for the Voxtype capture hook."""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LIMIT_MS = 100.0


def _run_once(hook: Path, state_root: Path, payload: bytes) -> float:
    environment = os.environ.copy()
    environment["ENGLISH_ER_STATE_ROOT"] = str(state_root)
    started = time.perf_counter_ns()
    completed = subprocess.run(
        [sys.executable, str(hook)],
        input=payload,
        capture_output=True,
        check=False,
        env=environment,
    )
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    if completed.returncode != 0 or completed.stdout != payload or completed.stderr:
        raise RuntimeError("capture hook failed benchmark correctness check")
    return elapsed_ms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=160)
    parser.add_argument("--warmup", type=int, default=16)
    arguments = parser.parse_args()
    if arguments.iterations < 20 or arguments.warmup < 1:
        parser.error("use at least 20 iterations and one warmup")

    hook = Path(__file__).with_name("english_er_capture.py")
    payload = "Exact café — punctuation!\nSecond line.\n".encode()
    with tempfile.TemporaryDirectory(prefix="english-er-hook-benchmark-") as temporary:
        state_root = Path(temporary) / "state"
        state_root.mkdir(mode=0o700)
        (state_root / "capture-enabled").touch(mode=0o600)
        for _ in range(arguments.warmup):
            _run_once(hook, state_root, payload)
        samples = [_run_once(hook, state_root, payload) for _ in range(arguments.iterations)]

    samples.sort()
    p95 = samples[math.ceil(len(samples) * 0.95) - 1]
    if p95 >= LIMIT_MS:
        print(f"capture benchmark failed: p95={p95:.2f} ms (limit < {LIMIT_MS:.0f} ms)")
        return 1
    print(f"capture benchmark passed: n={len(samples)} p95={p95:.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
