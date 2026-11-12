#!/usr/bin/env python3
"""Run an isolated API, real worker, and fake provider for Playwright."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from alembic.config import Config

from alembic import command
from english_er.entrypoints.http import create_app
from english_er.platform.resources import ApiRuntime
from english_er.modules.capture.ingestion import IngestionWorker
from english_er.modules.capture.spool import Spool
from english_er.modules.corrections.service import CorrectionProcessor
from english_er.infra.database import Database, sqlite_url
from english_er.modules.transcripts.result import Correction, CorrectionItem, CorrectionResult
from english_er.modules.corrections.worker import PersistentWorker


@dataclass(slots=True)
class FakeProvider:
    async def correct(self, transcript: str) -> CorrectionResult:
        wrong = "I has"
        corrected = transcript.replace(wrong, "I have")
        corrections = [CorrectionItem(wrong=wrong, correct="I have")] if wrong in transcript else []
        return CorrectionResult(
            correction=Correction(
                corrected_text=corrected,
                corrections=corrections,
                overall_observation="The fixture was corrected by the isolated fake provider.",
            ),
            provider="fake",
            model="fake-e2e",
            prompt_version="e2e-v1",
        )


@dataclass(slots=True)
class FakeSynthesizer:
    async def synthesize(self, _text: str, target: Path) -> None:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(b"RIFFfake-wave")

    async def close(self) -> None:
        return None


def _migrate(repository_root: Path, database_url: str) -> None:
    config = Config(repository_root / "apps" / "backend" / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


async def _serve() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    e2e_root_value = os.environ.get("ENGLISH_ER_E2E_ROOT")
    if not e2e_root_value:
        raise SystemExit("ENGLISH_ER_E2E_ROOT must name a temporary directory")
    e2e_root = Path(e2e_root_value).resolve()
    state_root = e2e_root / "state" / "english-er"
    data_root = e2e_root / "data" / "english-er"
    state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    data_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    database_url = sqlite_url(data_root / "english-er.sqlite3")
    await asyncio.to_thread(_migrate, repository_root, database_url)

    database = Database.create(database_url)
    stop = asyncio.Event()
    worker = PersistentWorker(
        IngestionWorker(Spool(state_root), database.sessions),
        CorrectionProcessor(database.sessions, FakeProvider(), retry_delay_seconds=0),
        poll_interval_seconds=0.05,
    )
    app = create_app(
        runtime=ApiRuntime(
            database=database,
            capture_marker=state_root / "capture-enabled",
            audio_root=e2e_root / "cache" / "english-er" / "tts",
            synthesizer=FakeSynthesizer(),
        ),
        static_root=repository_root / "apps" / "web" / "dist",
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8765,
            access_log=False,
            log_level="warning",
        )
    )
    worker_task = asyncio.create_task(worker.run_forever(stop=stop))
    try:
        await server.serve()
    finally:
        stop.set()
        await worker_task
        await database.close()


if __name__ == "__main__":
    asyncio.run(_serve())
