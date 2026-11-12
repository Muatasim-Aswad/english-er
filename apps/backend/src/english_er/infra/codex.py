"""Fresh-process Codex correction provider."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from english_er.infra.codex_errors import (
    classify_nonzero,
    execution_error,
    invalid_output_error,
    timeout_error,
)

CODEX_MODEL = "gpt-5.6-luna"
DEFAULT_TIMEOUT_SECONDS = 120.0
TERMINATION_GRACE_SECONDS = 5.0

ProcessFactory = Callable[..., Awaitable[asyncio.subprocess.Process]]


class CodexProcess:
    provider_name = "codex"

    def __init__(
        self,
        *,
        executable: str = "codex",
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        process_factory: ProcessFactory = asyncio.create_subprocess_exec,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.process_factory = process_factory

    async def execute(self, prompt: str, schema: dict[str, object]) -> bytes:
        with TemporaryDirectory(prefix="english-er-codex-") as temporary:
            root = Path(temporary)
            working_directory = root / "work"
            working_directory.mkdir()
            schema_path = root / "schema.json"
            result_path = root / "last-message.json"
            schema_path.write_text(
                json.dumps(schema),
                encoding="utf-8",
            )
            command = self._command(schema_path, result_path)
            try:
                process = await self.process_factory(
                    *command,
                    cwd=working_directory,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as error:
                raise execution_error() from error

            try:
                _stdout, stderr = await asyncio.wait_for(
                    process.communicate(prompt.encode("utf-8")),
                    timeout=self.timeout_seconds,
                )
            except asyncio.CancelledError:
                await self._terminate(process)
                raise
            except TimeoutError as error:
                await self._terminate(process)
                raise timeout_error() from error

            if process.returncode != 0:
                raise classify_nonzero(stderr or b"")

            try:
                return result_path.read_bytes()
            except OSError as error:
                raise invalid_output_error() from error

    def _command(self, schema_path: Path, result_path: Path) -> tuple[str, ...]:
        return (
            self.executable,
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--model",
            CODEX_MODEL,
            "-c",
            'model_reasoning_effort="low"',
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(result_path),
            "-",
        )

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            await process.wait()
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=TERMINATION_GRACE_SECONDS)
        except TimeoutError:
            process.kill()
            await process.wait()
