import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

from english_er.infra.kokoro import KokoroProcessSynthesizer
from english_er.infra.ownership import WorkerOwnership


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancellation_reap_the_speech_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    create_process = asyncio.create_subprocess_exec
    processes: list[asyncio.subprocess.Process] = []
    started = asyncio.Event()

    async def fake_process(*_args: str, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await create_process(
            sys.executable, "-c", "import sys,time; sys.stdin.readline(); time.sleep(60)", **kwargs
        )
        processes.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_process)
    synthesizer = KokoroProcessSynthesizer(timeout_seconds=60 if cancel else 0.1)
    target = tmp_path / "audio.wav"
    task = asyncio.create_task(synthesizer.synthesize("private transcript", target))
    await started.wait()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    assert processes[0].returncode is not None
    assert not target.exists()
    await synthesizer.close()


def test_worker_ownership_excludes_overlapping_recovery_and_releases(tmp_path: Path) -> None:
    with (
        WorkerOwnership(tmp_path),
        pytest.raises(RuntimeError, match="Another English-er worker"),
        WorkerOwnership(tmp_path),
    ):
        pytest.fail("A second worker acquired ownership")
    with WorkerOwnership(tmp_path):
        assert not (tmp_path / "capture-enabled").exists()
