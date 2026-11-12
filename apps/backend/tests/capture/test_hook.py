from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
HOOK = REPOSITORY_ROOT / "integrations" / "voxtype" / "english_er_capture.py"
BENCHMARK = REPOSITORY_ROOT / "integrations" / "voxtype" / "benchmark.py"


def run_hook(state_root: Path, payload: bytes) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["ENGLISH_ER_STATE_ROOT"] = str(state_root)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        check=False,
        env=environment,
    )


def test_disabled_echoes_exact_input_without_creating_state(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    payload = "Café — exact!\nSecond line.\n".encode()

    completed = run_hook(state_root, payload)

    assert completed.returncode == 0
    assert completed.stdout == payload
    assert completed.stderr == b""
    assert not state_root.exists()


def test_enabled_writes_exact_strict_envelope_and_permissions(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir(mode=0o755)
    (state_root / "capture-enabled").touch(mode=0o600)
    payload = "Café — exact punctuation!\nSecond line.\n".encode()

    completed = run_hook(state_root, payload)

    assert completed.returncode == 0
    assert completed.stdout == payload
    assert completed.stderr == b""
    captures = list((state_root / "spool" / "pending").glob("*.json"))
    assert len(captures) == 1
    envelope = json.loads(captures[0].read_bytes())
    assert set(envelope) == {"version", "id", "captured_at", "source", "text"}
    assert envelope["version"] == 1
    assert envelope["source"] == "voxtype"
    assert envelope["text"] == payload.decode()
    assert not list((state_root / "spool" / "pending").glob("*.tmp"))
    assert state_root.stat().st_mode & 0o777 == 0o700
    assert captures[0].stat().st_mode & 0o777 == 0o600
    for name in ("spool", "spool/pending", "spool/processing", "spool/failed"):
        assert (state_root / name).stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("payload", [b"private transcript", b"\xff\xfeinvalid utf8"])
def test_capture_error_echoes_exact_input_and_never_logs_text(
    tmp_path: Path, payload: bytes
) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "capture-enabled").touch()
    if payload.startswith(b"private"):
        (state_root / "spool").write_text("blocks directory creation")

    completed = run_hook(state_root, payload)

    assert completed.returncode == 0
    assert completed.stdout == payload
    assert completed.stderr.startswith(b"english-er capture failed:")
    assert b"private transcript" not in completed.stderr
    assert b"invalid utf8" not in completed.stderr


def test_dependency_free_warmed_benchmark(tmp_path: Path) -> None:
    del tmp_path
    completed = subprocess.run(
        [sys.executable, str(BENCHMARK), "--iterations", "40", "--warmup", "5"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.startswith("capture benchmark passed:")
