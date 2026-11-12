"""Durable transcript correction transitions."""

from dataclasses import dataclass
from datetime import datetime
from typing import TypeGuard
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.modules.transcripts.models import CorrectionResult as StoredCorrectionResult
from english_er.modules.transcripts.models import Transcript
from english_er.modules.transcripts.result import CorrectionResult
from english_er.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class PendingTranscript:
    id: UUID
    text: str
    revision: int
    attempt_count: int


class CorrectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_oldest(self, *, now: datetime | None = None) -> PendingTranscript | None:
        statement = (
            select(Transcript)
            .where(Transcript.status == ProcessingStatus.PENDING)
            .order_by(Transcript.queued_at, Transcript.id)
            .limit(1)
        )
        transcript = (await self.session.scalars(statement)).first()
        if transcript is None:
            return None
        return self._claim(transcript, now=now)

    async def claim(
        self,
        transcript_id: UUID,
        revision: int,
        *,
        now: datetime | None = None,
    ) -> PendingTranscript | None:
        transcript = await self.session.get(Transcript, transcript_id)
        if (
            transcript is None
            or transcript.status != ProcessingStatus.PENDING
            or transcript.text_revision != revision
        ):
            return None
        return self._claim(transcript, now=now)

    @staticmethod
    def _claim(transcript: Transcript, *, now: datetime | None = None) -> PendingTranscript:
        transcript.status = ProcessingStatus.PROCESSING
        transcript.attempt_count += 1
        transcript.updated_at = now or utc_now()
        return PendingTranscript(
            id=transcript.id,
            text=transcript.transcript_text,
            revision=transcript.text_revision,
            attempt_count=transcript.attempt_count,
        )

    async def complete(
        self,
        transcript_id: UUID,
        revision: int,
        result: CorrectionResult,
        *,
        now: datetime | None = None,
    ) -> bool:
        transcript = await self.session.get(Transcript, transcript_id)
        if not self._is_current_processing(transcript, revision):
            return False
        timestamp = now or utc_now()
        correction = result.correction
        await self.session.execute(
            delete(StoredCorrectionResult).where(
                StoredCorrectionResult.transcript_id == transcript_id
            )
        )
        self.session.add(
            StoredCorrectionResult(
                transcript_id=transcript.id,
                corrected_text=correction.corrected_text,
                corrections=[item.model_dump() for item in correction.corrections],
                overall_observation=correction.overall_observation,
                provider=result.provider,
                model=result.model,
                prompt_version=result.prompt_version,
                input_revision=revision,
                created_at=timestamp,
            )
        )
        transcript.status = ProcessingStatus.COMPLETED
        transcript.last_error = None
        transcript.updated_at = timestamp
        return True

    async def record_failure(
        self,
        transcript_id: UUID,
        revision: int,
        error: str,
        *,
        retry: bool,
        now: datetime | None = None,
    ) -> bool:
        transcript = await self.session.get(Transcript, transcript_id)
        if not self._is_current_processing(transcript, revision):
            return False
        transcript.status = ProcessingStatus.PENDING if retry else ProcessingStatus.FAILED
        transcript.last_error = error
        transcript.updated_at = now or utc_now()
        return True

    async def release(
        self,
        transcript_id: UUID,
        revision: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        transcript = await self.session.get(Transcript, transcript_id)
        if not self._is_current_processing(transcript, revision):
            return False
        transcript.status = ProcessingStatus.PENDING
        transcript.updated_at = now or utc_now()
        return True

    async def manual_retry(self, transcript_id: UUID, *, now: datetime | None = None) -> bool:
        transcript = await self.session.get(Transcript, transcript_id)
        if transcript is None or transcript.status != ProcessingStatus.FAILED:
            return False
        transcript.status = ProcessingStatus.PENDING
        transcript.attempt_count = 0
        transcript.last_error = None
        timestamp = now or utc_now()
        transcript.queued_at = timestamp
        transcript.updated_at = timestamp
        return True

    @staticmethod
    def _is_current_processing(
        transcript: Transcript | None,
        revision: int,
    ) -> TypeGuard[Transcript]:
        return bool(
            transcript is not None
            and transcript.status == ProcessingStatus.PROCESSING
            and transcript.text_revision == revision
        )
