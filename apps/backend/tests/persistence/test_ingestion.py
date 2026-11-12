from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from english_er.infra.database import Database, sqlite_url
from english_er.infra.orm import Base
from english_er.modules.capture.ingestion import IngestionResult, IngestionWorker
from english_er.modules.capture.spool import Spool
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.modules.transcripts.models import CorrectionResult, Transcript
from english_er.modules.transcripts.repository import TranscriptRepository
from english_er.shared.ids import uuid7


def write_capture(spool: Spool, *, capture_id: UUID | None = None, text: str = "exact") -> UUID:
    spool.ensure()
    capture_id = capture_id or uuid7()
    (spool.pending / f"{capture_id}.json").write_text(
        json.dumps(
            {
                "version": 1,
                "id": str(capture_id),
                "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "source": "voxtype",
                "text": text,
            }
        )
    )
    return capture_id


@pytest_asyncio.fixture
async def database(tmp_path: Path):  # type: ignore[no-untyped-def]
    value = Database.create(sqlite_url(tmp_path / "test.sqlite3"), busy_timeout_ms=1_234)
    async with value.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield value
    finally:
        await value.close()


@pytest.mark.asyncio
async def test_sqlite_pragmas_are_enabled(database: Database) -> None:
    async with database.engine.connect() as connection:
        foreign_keys = (await connection.exec_driver_sql("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = (await connection.exec_driver_sql("PRAGMA busy_timeout")).scalar_one()
        journal_mode = (await connection.exec_driver_sql("PRAGMA journal_mode")).scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 1_234
    assert journal_mode == "wal"


@pytest.mark.asyncio
async def test_ingestion_preserves_text_and_deletes_after_commit(
    tmp_path: Path,
    database: Database,
) -> None:
    spool = Spool(tmp_path / "state")
    capture_id = write_capture(spool, text="Café — exact!\nSecond line.\n")
    worker = IngestionWorker(spool, database.sessions)

    assert await worker.ingest_one() is IngestionResult.INSERTED
    assert not list(spool.processing.iterdir())
    async with database.sessions() as session:
        transcript = await session.get(Transcript, capture_id)
        assert transcript is not None
        assert transcript.original_text == "Café — exact!\nSecond line.\n"
        assert transcript.transcript_text == transcript.original_text
        assert transcript.text_revision == 1
        assert transcript.queued_at.tzinfo is UTC
        assert transcript.captured_at.tzinfo is UTC


@pytest.mark.asyncio
async def test_commit_before_delete_crash_window_is_idempotent(
    tmp_path: Path,
    database: Database,
) -> None:
    spool = Spool(tmp_path / "state")
    capture_id = write_capture(spool)
    claim = spool.claim_oldest()
    assert claim is not None
    async with database.sessions.begin() as session:
        assert await TranscriptRepository(session).add_capture(claim.envelope)
    assert claim.path.exists()

    worker = IngestionWorker(spool, database.sessions)
    assert await worker.recover() == (1, 0)
    assert await worker.ingest_one() is IngestionResult.DUPLICATE

    async with database.sessions() as session:
        count = await session.scalar(
            select(func.count()).select_from(Transcript).where(Transcript.id == capture_id)
        )
    assert count == 1
    assert not list(spool.processing.iterdir())
    assert not list(spool.pending.glob("*.json"))


@pytest.mark.asyncio
async def test_recovery_resets_interrupted_database_processing(
    tmp_path: Path,
    database: Database,
) -> None:
    spool = Spool(tmp_path / "state")
    capture_id = write_capture(spool)
    worker = IngestionWorker(spool, database.sessions)
    assert await worker.ingest_one() is IngestionResult.INSERTED
    async with database.sessions.begin() as session:
        transcript = await session.get(Transcript, capture_id)
        assert transcript is not None
        transcript.status = ProcessingStatus.PROCESSING

    assert await worker.recover() == (0, 1)
    async with database.sessions() as session:
        transcript = await session.get(Transcript, capture_id)
        assert transcript is not None
        assert transcript.status is ProcessingStatus.PENDING


@pytest.mark.asyncio
async def test_transcript_delete_cascades_correction_result(
    tmp_path: Path,
    database: Database,
) -> None:
    spool = Spool(tmp_path / "state")
    capture_id = write_capture(spool)
    worker = IngestionWorker(spool, database.sessions)
    assert await worker.ingest_one() is IngestionResult.INSERTED
    async with database.sessions.begin() as session:
        session.add(
            CorrectionResult(
                transcript_id=capture_id,
                corrected_text="corrected",
                corrections=[{"wrong": "exact", "correct": "corrected"}],
                overall_observation="Clear.",
                provider="test",
                model="test",
                prompt_version="1",
                input_revision=1,
            )
        )

    async with database.sessions.begin() as session:
        assert await TranscriptRepository(session).delete(capture_id)

    async with database.sessions() as session:
        assert await session.get(Transcript, capture_id) is None
        assert await session.get(CorrectionResult, capture_id) is None


@pytest.mark.asyncio
async def test_conflicting_capture_identity_is_preserved_for_inspection(
    tmp_path: Path, database: Database
) -> None:
    spool = Spool(tmp_path / "state")
    capture_id = write_capture(spool, text="Original capture.")
    worker = IngestionWorker(spool, database.sessions)
    assert await worker.ingest_one() is IngestionResult.INSERTED
    write_capture(spool, capture_id=capture_id, text="Conflicting capture.")
    assert await worker.ingest_one() is IngestionResult.CONFLICT
    failed = list(spool.failed.glob("*.json"))
    assert len(failed) == 1
    assert json.loads(failed[0].read_text())["text"] == "Conflicting capture."
    async with database.sessions() as session:
        row = await session.get(Transcript, capture_id)
        assert row is not None
        assert row.original_text == "Original capture."
