"""Sequential correction processing with bounded retries."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from english_er.modules.corrections.errors import (
    ProviderError,
    execution_error,
    invalid_output_error,
)
from english_er.modules.corrections.ports import CorrectionProvider
from english_er.modules.transcripts import CorrectionRepository, PendingTranscript, begin_write
from english_er.modules.transcripts import ProviderResult as CorrectionResult

DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_SECONDS = 10.0

Sleep = Callable[[float], Awaitable[None]]


class ProcessingResult(StrEnum):
    EMPTY = "empty"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


@dataclass(slots=True)
class CorrectionProcessor:
    sessions: async_sessionmaker[AsyncSession]
    provider: CorrectionProvider
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS
    sleep: Sleep = asyncio.sleep

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must not be negative")

    async def process_one(self) -> ProcessingResult:
        pending = await self._claim_oldest()
        if pending is None:
            return ProcessingResult.EMPTY

        while True:
            try:
                result = await self.provider.correct(pending.text)
                result.correction.validate_against(pending.text)
            except ProviderError as error:
                retry = error.retryable and pending.attempt_count < self.max_attempts
                if not await self._record_failure(pending, error, retry=retry):
                    return ProcessingResult.SUPERSEDED
                if not retry:
                    return ProcessingResult.FAILED
                await self.sleep(self.retry_delay_seconds)
                reclaimed = await self._claim(pending)
                if reclaimed is None:
                    return ProcessingResult.SUPERSEDED
                pending = reclaimed
                continue
            except ValueError:
                provider_error = invalid_output_error()
                retry = pending.attempt_count < self.max_attempts
                if not await self._record_failure(pending, provider_error, retry=retry):
                    return ProcessingResult.SUPERSEDED
                if not retry:
                    return ProcessingResult.FAILED
                await self.sleep(self.retry_delay_seconds)
                reclaimed = await self._claim(pending)
                if reclaimed is None:
                    return ProcessingResult.SUPERSEDED
                pending = reclaimed
                continue
            except Exception:
                provider_error = execution_error()
                retry = pending.attempt_count < self.max_attempts
                if not await self._record_failure(pending, provider_error, retry=retry):
                    return ProcessingResult.SUPERSEDED
                if not retry:
                    return ProcessingResult.FAILED
                await self.sleep(self.retry_delay_seconds)
                reclaimed = await self._claim(pending)
                if reclaimed is None:
                    return ProcessingResult.SUPERSEDED
                pending = reclaimed
                continue

            try:
                completed = await self._complete(pending, result)
            except Exception:
                await self._release(pending)
                raise
            return ProcessingResult.COMPLETED if completed else ProcessingResult.SUPERSEDED

    async def manual_retry(self, transcript_id: UUID) -> bool:
        async with self.sessions.begin() as session:
            await begin_write(session)
            return await CorrectionRepository(session).manual_retry(transcript_id)

    async def _claim_oldest(self) -> PendingTranscript | None:
        async with self.sessions.begin() as session:
            await begin_write(session)
            return await CorrectionRepository(session).claim_oldest()

    async def _claim(self, pending: PendingTranscript) -> PendingTranscript | None:
        async with self.sessions.begin() as session:
            await begin_write(session)
            return await CorrectionRepository(session).claim(pending.id, pending.revision)

    async def _complete(self, pending: PendingTranscript, result: CorrectionResult) -> bool:
        async with self.sessions.begin() as session:
            await begin_write(session)
            return await CorrectionRepository(session).complete(
                pending.id,
                pending.revision,
                result,
            )

    async def _record_failure(
        self,
        pending: PendingTranscript,
        error: ProviderError,
        *,
        retry: bool,
    ) -> bool:
        async with self.sessions.begin() as session:
            await begin_write(session)
            return await CorrectionRepository(session).record_failure(
                pending.id,
                pending.revision,
                error.storage_message,
                retry=retry,
            )

    async def _release(self, pending: PendingTranscript) -> None:
        async with self.sessions.begin() as session:
            await begin_write(session)
            await CorrectionRepository(session).release(pending.id, pending.revision)
