"""Application services for review, capture control, and health."""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from english_er.config import SYNTHESIS_PROFILE
from english_er.modules.transcripts.domain import ProcessingStatus, ReviewedState
from english_er.modules.transcripts.dto import (
    CorrectionPair,
    CorrectionResult,
    PageMetadata,
    TranscriptDetail,
    TranscriptPage,
    TranscriptSummary,
)
from english_er.modules.transcripts.health import DatabaseHealth, HealthResponse
from english_er.modules.transcripts.models import Transcript
from english_er.modules.transcripts.processing_repository import CorrectionRepository
from english_er.modules.transcripts.repository import TranscriptRepository
from english_er.modules.transcripts.review_repository import ReviewRepository
from english_er.modules.transcripts.storage import remove_audio_files
from english_er.modules.transcripts.transactions import begin_write
from english_er.shared.errors import AppError
from english_er.shared.time import utc_now

PREVIEW_LIMIT = 160


def _database_unavailable() -> AppError:
    return AppError("database_unavailable", "The transcript database is unavailable.")


def _not_found() -> AppError:
    return AppError("not_found", "Transcript not found.")


def _encode_cursor(
    transcript: Transcript, status: ProcessingStatus | None, reviewed: ReviewedState | None
) -> str:
    payload = json.dumps(
        {
            "captured_at": transcript.captured_at.isoformat(),
            "id": str(transcript.id),
            "status": status,
            "reviewed": reviewed,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def _decode_cursor(
    cursor: str, status: ProcessingStatus | None, reviewed: ReviewedState | None
) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.b64decode(cursor + padding, altchars=b"-_", validate=True)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            "captured_at",
            "id",
            "status",
            "reviewed",
        }:
            raise ValueError
        if not isinstance(payload["captured_at"], str) or not isinstance(payload["id"], str):
            raise ValueError
        if payload["status"] != status or payload["reviewed"] != reviewed:
            raise ValueError
        captured_at = datetime.fromisoformat(payload["captured_at"])
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError
        return captured_at.astimezone(UTC), UUID(payload["id"])
    except (binascii.Error, UnicodeError, ValueError, json.JSONDecodeError, TypeError) as error:
        raise AppError("invalid_cursor", "The pagination cursor is invalid.") from error


def _summary(transcript: Transcript) -> TranscriptSummary:
    return TranscriptSummary(
        id=transcript.id,
        source="voxtype",
        preview=transcript.transcript_text[:PREVIEW_LIMIT],
        captured_at=transcript.captured_at,
        reviewed_at=transcript.reviewed_at,
        status=transcript.status,
        attempt_count=transcript.attempt_count,
        last_error=transcript.last_error,
    )


def _detail(transcript: Transcript) -> TranscriptDetail:
    stored = transcript.correction
    correction = None
    if stored is not None:
        correction = CorrectionResult(
            corrected_text=stored.corrected_text,
            corrections=[CorrectionPair.model_validate(item) for item in stored.corrections],
            overall_observation=stored.overall_observation,
            audio_available=any(
                asset.synthesis_profile == SYNTHESIS_PROFILE for asset in stored.audio_assets
            ),
            provider=stored.provider,
            model=stored.model,
            prompt_version=stored.prompt_version,
            input_revision=stored.input_revision,
            created_at=stored.created_at,
        )
    return TranscriptDetail(
        preview=transcript.transcript_text[:PREVIEW_LIMIT],
        id=transcript.id,
        source="voxtype",
        original_text=transcript.original_text,
        transcript_text=transcript.transcript_text,
        text_revision=transcript.text_revision,
        captured_at=transcript.captured_at,
        reviewed_at=transcript.reviewed_at,
        status=transcript.status,
        attempt_count=transcript.attempt_count,
        last_error=transcript.last_error,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
        correction=correction,
    )


@dataclass(slots=True)
class ReviewService:
    sessions: async_sessionmaker[AsyncSession]
    audio_root: Path | None = None

    async def health(self) -> HealthResponse:
        try:
            async with self.sessions() as session:
                await ReviewRepository(session).check_schema()
        except (OSError, SQLAlchemyError):
            return HealthResponse(database=DatabaseHealth.UNAVAILABLE)
        return HealthResponse(database=DatabaseHealth.OK)

    async def list_transcripts(
        self,
        *,
        cursor: str | None,
        limit: int,
        status: ProcessingStatus | None,
        reviewed: ReviewedState | None,
    ) -> TranscriptPage:
        before = _decode_cursor(cursor, status, reviewed) if cursor is not None else None
        try:
            async with self.sessions() as session:
                page = await ReviewRepository(session).list(
                    limit=limit,
                    status=status,
                    reviewed=reviewed,
                    before=before,
                )
        except (OSError, SQLAlchemyError) as error:
            raise _database_unavailable() from error
        next_cursor = (
            _encode_cursor(page.items[-1], status, reviewed)
            if page.has_more and page.items
            else None
        )
        return TranscriptPage(
            items=[_summary(item) for item in page.items],
            metadata=PageMetadata(next_cursor=next_cursor),
        )

    async def get_transcript(self, transcript_id: UUID) -> TranscriptDetail:
        try:
            async with self.sessions() as session:
                transcript = await ReviewRepository(session).get_detail(transcript_id)
        except (OSError, SQLAlchemyError) as error:
            raise _database_unavailable() from error
        if transcript is None:
            raise _not_found()
        return _detail(transcript)

    async def set_reviewed(self, transcript_id: UUID, reviewed: bool) -> TranscriptDetail:
        try:
            async with self.sessions.begin() as session:
                await begin_write(session)
                transcript = await ReviewRepository(session).get_detail(transcript_id)
                if transcript is None:
                    raise _not_found()
                if reviewed and transcript.reviewed_at is None:
                    transcript.reviewed_at = utc_now()
                    transcript.updated_at = transcript.reviewed_at
                elif not reviewed and transcript.reviewed_at is not None:
                    transcript.reviewed_at = None
                    transcript.updated_at = utc_now()
                await session.flush()
                result = _detail(transcript)
        except AppError:
            raise
        except (OSError, SQLAlchemyError) as error:
            raise _database_unavailable() from error
        return result

    async def update_text(
        self,
        transcript_id: UUID,
        text: str,
        expected_revision: int,
    ) -> TranscriptDetail:
        audio_paths: list[str] = []
        try:
            async with self.sessions.begin() as session:
                await begin_write(session)
                transcript = await ReviewRepository(session).get_detail(transcript_id)
                if transcript is None:
                    raise _not_found()
                if transcript.text_revision != expected_revision:
                    raise AppError(
                        "revision_conflict",
                        "The transcript was changed by another request.",
                        public={"current_revision": transcript.text_revision},
                    )
                if transcript.transcript_text == text:
                    return _detail(transcript)

                audio_paths = await ReviewRepository(session).audio_paths(transcript_id)
                timestamp = utc_now()
                transcript.transcript_text = text
                transcript.text_revision += 1
                transcript.queued_at = timestamp
                transcript.status = ProcessingStatus.PENDING
                transcript.attempt_count = 0
                transcript.last_error = None
                transcript.reviewed_at = None
                transcript.updated_at = timestamp
                transcript.correction = None
                await session.flush()
                result = _detail(transcript)
        except AppError:
            raise
        except (OSError, SQLAlchemyError) as error:
            raise _database_unavailable() from error
        if self.audio_root is not None:
            remove_audio_files(self.audio_root, audio_paths)
        return result

    async def retry(self, transcript_id: UUID) -> TranscriptSummary:
        try:
            async with self.sessions.begin() as session:
                await begin_write(session)
                transcript = await TranscriptRepository(session).get(transcript_id)
                if transcript is None:
                    raise _not_found()
                if transcript.status != ProcessingStatus.FAILED:
                    raise AppError(
                        "invalid_state",
                        "Only failed transcripts can be retried.",
                    )
                if not await CorrectionRepository(session).manual_retry(transcript_id):
                    raise AppError("invalid_state", "The transcript state changed.")
                await session.flush()
                result = _summary(transcript)
        except AppError:
            raise
        except (OSError, SQLAlchemyError) as error:
            raise _database_unavailable() from error
        return result

    async def delete(self, transcript_id: UUID) -> None:
        audio_paths: list[str] = []
        try:
            async with self.sessions.begin() as session:
                await begin_write(session)
                audio_paths = await ReviewRepository(session).audio_paths(transcript_id)
                if not await TranscriptRepository(session).delete(transcript_id):
                    raise _not_found()
        except AppError:
            raise
        except (OSError, SQLAlchemyError) as error:
            raise _database_unavailable() from error
        if self.audio_root is not None:
            remove_audio_files(self.audio_root, audio_paths)
