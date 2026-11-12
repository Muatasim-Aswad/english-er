import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from english_er.modules.capture import IngestionResult, IngestionWorker
from english_er.modules.corrections.service import CorrectionProcessor, ProcessingResult

DEFAULT_POLL_INTERVAL_SECONDS = 1.0
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    spool_files: int
    database_rows: int


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    ingestion: IngestionResult
    correction: ProcessingResult

    @property
    def idle(self) -> bool:
        return self.ingestion == IngestionResult.EMPTY and self.correction == ProcessingResult.EMPTY


@dataclass(slots=True)
class PersistentWorker:
    ingestion: IngestionWorker
    corrections: CorrectionProcessor
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    sleep: Sleep = asyncio.sleep

    def __post_init__(self) -> None:
        if self.poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds must not be negative")

    async def recover(self) -> RecoveryResult:
        spool_files, database_rows = await self.ingestion.recover()
        return RecoveryResult(spool_files=spool_files, database_rows=database_rows)

    async def run_once(self) -> WorkerCycleResult:
        ingestion = await self.ingestion.ingest_one()
        correction = await self.corrections.process_one()
        return WorkerCycleResult(ingestion=ingestion, correction=correction)

    async def run_forever(self, *, stop: asyncio.Event | None = None) -> None:
        await self.recover()
        while stop is None or not stop.is_set():
            cycle = await self.run_once()
            if cycle.idle:
                await self.sleep(self.poll_interval_seconds)
