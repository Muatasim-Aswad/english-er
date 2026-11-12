"""Commit-before-delete ingestion for the persistent worker."""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from english_er.modules.capture.spool import Spool
from english_er.modules.transcripts import TranscriptRepository
from english_er.shared.errors import AppError


class IngestionResult(StrEnum):
    EMPTY = "empty"
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(slots=True)
class IngestionWorker:
    spool: Spool
    sessions: async_sessionmaker[AsyncSession]

    async def recover(self) -> tuple[int, int]:
        recovered_files = self.spool.recover_processing()
        async with self.sessions.begin() as session:
            reset_rows = await TranscriptRepository(session).reset_processing()
        return recovered_files, reset_rows

    async def ingest_one(self) -> IngestionResult:
        claim = self.spool.claim_oldest()
        if claim is None:
            return IngestionResult.EMPTY

        try:
            async with self.sessions.begin() as session:
                inserted = await TranscriptRepository(session).add_capture(claim.envelope)
        except AppError as error:
            if error.code != "capture_conflict":
                raise
            self.spool.quarantine(claim)
            return IngestionResult.CONFLICT

        # The transaction context commits before the durable claim is deleted.
        self.spool.complete(claim)
        return IngestionResult.INSERTED if inserted else IngestionResult.DUPLICATE
