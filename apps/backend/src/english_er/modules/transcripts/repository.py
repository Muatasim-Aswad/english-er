"""Persistence operations shared by ingestion and correction processing."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from english_er.modules.transcripts.capture import CaptureEnvelope
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.modules.transcripts.models import Transcript
from english_er.shared.errors import AppError
from english_er.shared.time import utc_now


class TranscriptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_capture(
        self,
        envelope: CaptureEnvelope,
        *,
        now: datetime | None = None,
    ) -> bool:
        timestamp = now or utc_now()
        statement = (
            sqlite_insert(Transcript)
            .values(
                id=envelope.id,
                source=envelope.source,
                original_text=envelope.text,
                transcript_text=envelope.text,
                text_revision=1,
                captured_at=envelope.captured_at,
                queued_at=timestamp,
                status=ProcessingStatus.PENDING,
                attempt_count=0,
                created_at=timestamp,
                updated_at=timestamp,
            )
            .on_conflict_do_nothing(index_elements=[Transcript.id])
        )
        result = await self.session.execute(statement)
        inserted = bool(result.rowcount == 1)  # type: ignore[attr-defined]
        if not inserted:
            existing = await self.session.get(Transcript, envelope.id)
            if existing is None or (
                existing.original_text,
                existing.captured_at,
                existing.source,
            ) != (envelope.text, envelope.captured_at, envelope.source):
                raise AppError(
                    "capture_conflict", "The capture identity was reused with different content."
                )
        return inserted

    async def get(self, transcript_id: UUID) -> Transcript | None:
        return await self.session.get(Transcript, transcript_id)

    async def reset_processing(self, *, now: datetime | None = None) -> int:
        result = await self.session.execute(
            update(Transcript)
            .where(Transcript.status == ProcessingStatus.PROCESSING)
            .values(status=ProcessingStatus.PENDING, updated_at=now or utc_now())
        )
        return int(result.rowcount)  # type: ignore[attr-defined]

    async def delete(self, transcript_id: UUID) -> bool:
        result = await self.session.execute(
            delete(Transcript).where(Transcript.id == transcript_id)
        )
        return bool(result.rowcount == 1)  # type: ignore[attr-defined]
