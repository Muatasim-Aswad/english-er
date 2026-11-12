"""Lazy resource composition; constructing the app has no filesystem side effects."""

import asyncio
from contextlib import suppress
from pathlib import Path

from english_er.config import Settings
from english_er.infra.database import Database, sqlite_url
from english_er.infra.kokoro import KokoroProcessSynthesizer
from english_er.platform.resources import ApiRuntime


class RuntimeProvider:
    """Return an injected runtime or create the default runtime on first request."""

    def __init__(
        self,
        *,
        settings: Settings,
        runtime: ApiRuntime | None = None,
        database_path: Path | None = None,
        capture_marker: Path | None = None,
        audio_root: Path | None = None,
    ) -> None:
        if runtime is not None and (
            database_path is not None or capture_marker is not None or audio_root is not None
        ):
            raise ValueError("runtime cannot be combined with runtime paths")
        self.settings = settings
        self._runtime = runtime
        self._database_path = database_path
        self._capture_marker = capture_marker
        self._audio_root = audio_root
        self._owns_runtime = runtime is None
        self._lock = asyncio.Lock()

    async def get(self) -> ApiRuntime:
        if self._runtime is not None:
            return self._runtime
        async with self._lock:
            if self._runtime is None:
                database_path = self._database_path or self.settings.database_path
                # Database checks and operations translate an unusable path into their public
                # health or service-unavailable response.
                with suppress(OSError):
                    database_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                self._runtime = ApiRuntime(
                    database=Database.create(
                        sqlite_url(database_path)
                        if self._database_path is not None
                        else (self.settings.database_url or sqlite_url(database_path))
                    ),
                    capture_marker=self._capture_marker or self.settings.capture_marker,
                    audio_root=self._audio_root or self.settings.audio_root,
                    synthesizer=KokoroProcessSynthesizer(
                        timeout_seconds=self.settings.speech_timeout
                    ),
                    speech_timeout=self.settings.speech_timeout,
                    speech_queue_timeout=self.settings.speech_queue_timeout,
                )
        return self._runtime

    async def close(self) -> None:
        if self._owns_runtime and self._runtime is not None:
            try:
                if self._runtime.synthesizer is not None:
                    await self._runtime.synthesizer.close()
            finally:
                await self._runtime.database.close()
