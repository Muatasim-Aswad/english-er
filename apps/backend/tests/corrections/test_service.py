"""Persistent correction transitions and retry policy."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from english_er.infra.database import Database, sqlite_url
from english_er.infra.orm import Base
from english_er.modules.corrections.errors import ProviderError, ProviderErrorCategory
from english_er.modules.corrections.service import CorrectionProcessor, ProcessingResult
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.modules.transcripts.models import CorrectionResult as StoredCorrectionResult
from english_er.modules.transcripts.models import Transcript
from english_er.modules.transcripts.processing_repository import CorrectionRepository
from english_er.modules.transcripts.result import Correction, CorrectionItem, CorrectionResult
from english_er.modules.transcripts.service import ReviewService
from english_er.shared.ids import uuid7


@dataclass(slots=True)
class FakeProvider:
    responses: list[CorrectionResult | ProviderError | Exception]
    calls: list[str] = field(default_factory=list)

    async def correct(self, transcript: str) -> CorrectionResult:
        self.calls.append(transcript)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def valid_result() -> CorrectionResult:
    return CorrectionResult(
        correction=Correction(
            corrected_text="I went home.",
            corrections=[CorrectionItem(wrong="go", correct="went")],
            overall_observation="Past tense was corrected.",
        ),
        provider="fake",
        model="fake-model",
        prompt_version="test-v1",
    )


async def make_database(tmp_path: Path) -> Database:
    database = Database.create(sqlite_url(tmp_path / "test.sqlite3"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return database


async def add_transcript(
    sessions: async_sessionmaker[AsyncSession],
    *,
    status: ProcessingStatus = ProcessingStatus.PENDING,
    attempt_count: int = 0,
) -> UUID:
    transcript_id = uuid7()
    async with sessions.begin() as session:
        session.add(
            Transcript(
                id=transcript_id,
                source="voxtype",
                original_text="I go home.",
                transcript_text="I go home.",
                text_revision=1,
                captured_at=datetime.now(UTC),
                queued_at=datetime.now(UTC),
                status=status,
                attempt_count=attempt_count,
            )
        )
    return transcript_id


@pytest.mark.asyncio
async def test_success_stores_only_validated_result_and_metadata(tmp_path: Path) -> None:
    database = await make_database(tmp_path)
    try:
        transcript_id = await add_transcript(database.sessions)
        processor = CorrectionProcessor(database.sessions, FakeProvider([valid_result()]))

        assert await processor.process_one() == ProcessingResult.COMPLETED

        async with database.sessions() as session:
            transcript = await session.get(Transcript, transcript_id)
            stored = await session.get(StoredCorrectionResult, transcript_id)
        assert transcript is not None and transcript.status == ProcessingStatus.COMPLETED
        assert transcript.attempt_count == 1
        assert transcript.last_error is None
        assert stored is not None
        assert stored.corrections == [{"wrong": "go", "correct": "went"}]
        assert stored.provider == "fake"
        assert stored.model == "fake-model"
        assert stored.prompt_version == "test-v1"
        assert stored.input_revision == 1
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_retryable_failure_waits_then_succeeds(tmp_path: Path) -> None:
    database = await make_database(tmp_path)
    delays: list[float] = []

    async def delay(seconds: float) -> None:
        delays.append(seconds)

    try:
        transcript_id = await add_transcript(database.sessions)
        failure = ProviderError(ProviderErrorCategory.EXECUTION, "temporary", retryable=True)
        provider = FakeProvider([failure, valid_result()])
        processor = CorrectionProcessor(database.sessions, provider, sleep=delay)

        assert await processor.process_one() == ProcessingResult.COMPLETED
        assert delays == [10.0]
        assert provider.calls == ["I go home.", "I go home."]
        async with database.sessions() as session:
            transcript = await session.get(Transcript, transcript_id)
        assert transcript is not None and transcript.attempt_count == 2
    finally:
        await database.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses",
    [
        [
            ProviderError(ProviderErrorCategory.INVALID_OUTPUT, "invalid", retryable=True),
            ProviderError(ProviderErrorCategory.TIMEOUT, "timeout", retryable=True),
        ],
        [RuntimeError("unexpected"), RuntimeError("unexpected")],
    ],
)
async def test_retry_exhaustion_fails_without_raw_output(
    tmp_path: Path,
    responses: Sequence[ProviderError | Exception],
) -> None:
    database = await make_database(tmp_path)

    async def no_delay(_seconds: float) -> None:
        return None

    try:
        transcript_id = await add_transcript(database.sessions)
        processor = CorrectionProcessor(
            database.sessions, FakeProvider(list(responses)), sleep=no_delay
        )
        assert await processor.process_one() == ProcessingResult.FAILED
        async with database.sessions() as session:
            transcript = await session.get(Transcript, transcript_id)
            stored = await session.get(StoredCorrectionResult, transcript_id)
        assert transcript is not None and transcript.status == ProcessingStatus.FAILED
        assert transcript.attempt_count == 2
        assert transcript.last_error in {
            "timeout: timeout",
            "execution: correction provider execution failed",
        }
        assert stored is None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_permanent_failure_does_not_retry_and_manual_retry_resets_attempts(
    tmp_path: Path,
) -> None:
    database = await make_database(tmp_path)
    try:
        transcript_id = await add_transcript(database.sessions)
        failure = ProviderError(ProviderErrorCategory.QUOTA, "quota unavailable", retryable=False)
        provider = FakeProvider([failure])
        processor = CorrectionProcessor(database.sessions, provider)

        assert await processor.process_one() == ProcessingResult.FAILED
        assert provider.calls == ["I go home."]
        assert await processor.manual_retry(transcript_id) is True

        async with database.sessions() as session:
            transcript = await session.get(Transcript, transcript_id)
        assert transcript is not None and transcript.status == ProcessingStatus.PENDING
        assert transcript.attempt_count == 0
        assert transcript.last_error is None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_manual_retry_rejects_nonfailed_transcript(tmp_path: Path) -> None:
    database = await make_database(tmp_path)
    try:
        transcript_id = await add_transcript(database.sessions)
        async with database.sessions.begin() as session:
            retried = await CorrectionRepository(session).manual_retry(transcript_id)
        assert retried is False
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_edit_during_provider_call_supersedes_stale_result(tmp_path: Path) -> None:
    database = await make_database(tmp_path)

    @dataclass(slots=True)
    class EditingProvider:
        calls: list[str] = field(default_factory=list)

        async def correct(self, transcript: str) -> CorrectionResult:
            self.calls.append(transcript)
            if len(self.calls) == 1:
                await ReviewService(database.sessions).update_text(
                    transcript_id,
                    "I went home.",
                    1,
                )
                return valid_result()
            return CorrectionResult(
                correction=Correction(
                    corrected_text="I went home.",
                    corrections=[],
                    overall_observation="No correction was needed.",
                ),
                provider="fake",
                model="fake-model",
                prompt_version="test-v1",
            )

    try:
        transcript_id = await add_transcript(database.sessions)
        provider = EditingProvider()
        processor = CorrectionProcessor(database.sessions, provider)

        assert await processor.process_one() == ProcessingResult.SUPERSEDED
        async with database.sessions() as session:
            transcript = await session.get(Transcript, transcript_id)
            stored = await session.get(StoredCorrectionResult, transcript_id)
        assert transcript is not None
        assert transcript.status == ProcessingStatus.PENDING
        assert transcript.text_revision == 2
        assert stored is None

        assert await processor.process_one() == ProcessingResult.COMPLETED
        assert provider.calls == ["I go home.", "I went home."]
        async with database.sessions() as session:
            stored = await session.get(StoredCorrectionResult, transcript_id)
        assert stored is not None and stored.input_revision == 2
    finally:
        await database.close()
