"""Database operations for the local review API."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from english_er.modules.transcripts.domain import ProcessingStatus, ReviewedState
from english_er.modules.transcripts.models import AudioAsset, CorrectionResult, Transcript


@dataclass(frozen=True, slots=True)
class TranscriptSlice:
    items: list[Transcript]
    has_more: bool


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check_schema(self) -> None:
        for model in (Transcript, CorrectionResult, AudioAsset):
            await self.session.execute(select(model).limit(0))

    async def list(
        self,
        *,
        limit: int,
        status: ProcessingStatus | None,
        reviewed: ReviewedState | None,
        before: tuple[datetime, UUID] | None,
    ) -> TranscriptSlice:
        statement = select(Transcript)
        if status is not None:
            statement = statement.where(Transcript.status == status)
        if reviewed == ReviewedState.REVIEWED:
            statement = statement.where(Transcript.reviewed_at.is_not(None))
        elif reviewed == ReviewedState.UNREVIEWED:
            statement = statement.where(Transcript.reviewed_at.is_(None))
        if before is not None:
            captured_at, transcript_id = before
            statement = statement.where(
                or_(
                    Transcript.captured_at < captured_at,
                    and_(Transcript.captured_at == captured_at, Transcript.id < transcript_id),
                )
            )
        statement = statement.order_by(Transcript.captured_at.desc(), Transcript.id.desc()).limit(
            limit + 1
        )
        rows = list((await self.session.scalars(statement)).all())
        return TranscriptSlice(items=rows[:limit], has_more=len(rows) > limit)

    async def get_detail(self, transcript_id: UUID) -> Transcript | None:
        statement = (
            select(Transcript)
            .where(Transcript.id == transcript_id)
            .options(
                selectinload(Transcript.correction).selectinload(CorrectionResult.audio_assets)
            )
        )
        return (await self.session.scalars(statement)).one_or_none()

    async def audio_paths(self, transcript_id: UUID) -> builtins.list[str]:
        statement = select(AudioAsset.relative_path).where(
            AudioAsset.correction_transcript_id == transcript_id
        )
        return list((await self.session.scalars(statement)).all())
