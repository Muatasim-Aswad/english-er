"""Persistent worker recovery and sequential processing."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from english_er.infra.database import Database, sqlite_url
from english_er.infra.orm import Base
from english_er.modules.capture.ingestion import IngestionResult, IngestionWorker
from english_er.modules.capture.spool import Spool
from english_er.modules.corrections.service import CorrectionProcessor, ProcessingResult
from english_er.modules.corrections.worker import PersistentWorker
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.modules.transcripts.models import Transcript
from english_er.modules.transcripts.result import Correction, CorrectionResult
from english_er.shared.ids import uuid7


@dataclass(slots=True)
class SequentialProvider:
    active: int = 0
    maximum_active: int = 0
    calls: list[str] = field(default_factory=list)

    async def correct(self, transcript: str) -> CorrectionResult:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        self.calls.append(transcript)
        await asyncio.sleep(0)
        self.active -= 1
        return CorrectionResult(
            correction=Correction(
                corrected_text=transcript,
                corrections=[],
                overall_observation="No correction was needed.",
            ),
            provider="fake",
            model="fake",
            prompt_version="test",
        )


async def make_worker(tmp_path: Path) -> tuple[Database, PersistentWorker, SequentialProvider]:
    database = Database.create(sqlite_url(tmp_path / "test.sqlite3"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    provider = SequentialProvider()
    ingestion = IngestionWorker(Spool(tmp_path / "state"), database.sessions)
    corrections = CorrectionProcessor(database.sessions, provider)
    return database, PersistentWorker(ingestion, corrections), provider


@pytest.mark.asyncio
async def test_startup_recovery_resets_processing_rows(tmp_path: Path) -> None:
    database, worker, _provider = await make_worker(tmp_path)
    try:
        transcript_id = uuid7()
        async with database.sessions.begin() as session:
            session.add(
                Transcript(
                    id=transcript_id,
                    source="voxtype",
                    original_text="Interrupted",
                    transcript_text="Interrupted",
                    text_revision=1,
                    captured_at=datetime.now(UTC),
                    queued_at=datetime.now(UTC),
                    status=ProcessingStatus.PROCESSING,
                    attempt_count=1,
                )
            )

        recovered = await worker.recover()

        assert recovered.database_rows == 1
        async with database.sessions() as session:
            transcript = await session.get(Transcript, transcript_id)
        assert transcript is not None and transcript.status == ProcessingStatus.PENDING
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_worker_processes_transcripts_one_at_a_time(tmp_path: Path) -> None:
    database, worker, provider = await make_worker(tmp_path)
    try:
        async with database.sessions.begin() as session:
            for text in ("First", "Second"):
                session.add(
                    Transcript(
                        id=uuid7(),
                        source="voxtype",
                        original_text=text,
                        transcript_text=text,
                        text_revision=1,
                        captured_at=datetime.now(UTC),
                        queued_at=datetime.now(UTC),
                        status=ProcessingStatus.PENDING,
                        attempt_count=0,
                    )
                )

        first = await worker.run_once()
        second = await worker.run_once()

        assert first.ingestion == IngestionResult.EMPTY
        assert first.correction == ProcessingResult.COMPLETED
        assert second.correction == ProcessingResult.COMPLETED
        assert provider.calls == ["First", "Second"]
        assert provider.maximum_active == 1
        async with database.sessions() as session:
            rows = list(await session.scalars(select(Transcript)))
        assert len(rows) == 2
    finally:
        await database.close()
