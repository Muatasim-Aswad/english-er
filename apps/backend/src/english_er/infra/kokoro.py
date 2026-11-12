"""Isolated, persistent Kokoro GPU synthesis process."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from english_er.config import SAMPLE_RATE, VOICE

_pipeline: Any | None = None


def _synthesize_kokoro(text: str, target: str) -> None:
    global _pipeline

    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    if _pipeline is None:
        _pipeline = KPipeline(
            lang_code="a",
            repo_id="hexgrad/Kokoro-82M",
            device="cuda",
        )
    segments = [np.asarray(audio, dtype=np.float32) for _, _, audio in _pipeline(text, voice=VOICE)]
    if not segments:
        raise RuntimeError("Kokoro produced no audio")
    silence = np.zeros(round(SAMPLE_RATE * 0.12), dtype=np.float32)
    joined: list[Any] = []
    for index, segment in enumerate(segments):
        if index:
            joined.append(silence)
        joined.append(segment)
    sf.write(target, np.concatenate(joined), SAMPLE_RATE, format="WAV", subtype="PCM_16")


class KokoroProcessSynthesizer:
    """Own one persistent child; deadlines and cancellation terminate its GPU work."""

    def __init__(self, *, timeout_seconds: float = 120) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self.timeout_seconds = timeout_seconds

    async def synthesize(self, text: str, target: Path) -> None:
        async with self._lock:
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    await self._request(text, target)
            except BaseException:
                await self.close()
                raise

    async def _request(self, text: str, target: Path) -> None:
        if self._process is None or self._process.returncode is not None:
            self._process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "english_er.infra.kokoro",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        process = self._process
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write((json.dumps({"text": text, "target": str(target)}) + "\n").encode())
        await process.stdin.drain()
        response = await process.stdout.readline()
        if response != b'{"ok": true}\n':
            raise RuntimeError("Speech synthesis failed")

    async def close(self) -> None:
        process, self._process = self._process, None
        if process is None or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=2)


def _child_main() -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with redirect_stdout(sys.stderr):
                _synthesize_kokoro(request["text"], request["target"])
            print(json.dumps({"ok": True}), flush=True)
        except Exception:
            print(json.dumps({"ok": False}), flush=True)


def prepare_main() -> None:
    """Download, load, and smoke-test the configured production voice."""

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    with tempfile.TemporaryDirectory(prefix="english-er-speech-") as directory:
        _synthesize_kokoro("English-er speech is ready.", str(Path(directory) / "ready.wav"))
    print("Prepared Kokoro-82M af_heart on CUDA")


if __name__ == "__main__":
    _child_main()
