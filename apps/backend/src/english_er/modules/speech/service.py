"""Persist and reuse correction-owned audio assets."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from english_er.config import SYNTHESIS_PROFILE
from english_er.modules.transcripts import AudioAsset, CorrectionResult, Transcript, begin_write
from english_er.shared.errors import AppError
from english_er.shared.ids import uuid7
from english_er.shared.speech import SpeechSynthesizer


class AudioService:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        audio_root: Path,
        synthesizer: SpeechSynthesizer,
        lock: asyncio.Lock,
        *,
        queue_timeout: float = 5,
        synthesis_timeout: float = 120,
    ) -> None:
        self.sessions = sessions
        self.audio_root = audio_root
        self.synthesizer = synthesizer
        self.lock = lock
        self.queue_timeout = queue_timeout
        self.synthesis_timeout = synthesis_timeout

    async def get_or_generate(self, transcript_id: UUID, expected_revision: int) -> Path:
        try:
            await asyncio.wait_for(self.lock.acquire(), timeout=self.queue_timeout)
        except TimeoutError as error:
            raise AppError("busy", "Speech generation is busy. Try again shortly.") from error
        try:
            cached = await self._cached(transcript_id, expected_revision)
            if cached is not None:
                return cached
            return await self._generate(transcript_id, expected_revision)
        finally:
            self.lock.release()

    async def _cached(self, transcript_id: UUID, expected_revision: int) -> Path | None:
        try:
            async with self.sessions.begin() as session:
                await begin_write(session)
                correction = await self._correction(session, transcript_id)
                await self._validate(session, transcript_id, correction, expected_revision)
                asset = self._profile_asset(correction)
                if asset is None:
                    return None
                path = self._asset_path(asset.relative_path)
                if path.is_file():
                    return path
                await session.delete(asset)
                return None
        except AppError:
            raise
        except (OSError, SQLAlchemyError) as error:
            raise AppError("speech_unavailable", "Speech storage is unavailable.") from error

    async def _generate(self, transcript_id: UUID, expected_revision: int) -> Path:
        try:
            async with self.sessions() as session:
                correction = await self._correction(session, transcript_id)
                await self._validate(session, transcript_id, correction, expected_revision)
                assert correction is not None
                text = correction.corrected_text
        except AppError:
            raise
        except SQLAlchemyError as error:
            raise AppError("speech_unavailable", "Speech storage is unavailable.") from error

        asset_id = uuid7()
        relative_path = f"{asset_id}.wav"
        final_path = self._asset_path(relative_path)
        temporary_path = self.audio_root / f".{asset_id}.tmp"
        final_created = False
        try:
            self._prepare_root()
            try:
                await asyncio.wait_for(
                    self.synthesizer.synthesize(text, temporary_path),
                    timeout=self.synthesis_timeout,
                )
            except TimeoutError as error:
                raise AppError("speech_timeout", "Speech generation timed out.") from error
            temporary_path.chmod(0o600)
            if temporary_path.stat().st_size == 0:
                raise OSError("generated audio is empty")

            async with self.sessions.begin() as session:
                await begin_write(session)
                correction = await self._correction(session, transcript_id)
                await self._validate(session, transcript_id, correction, expected_revision)
                existing = self._profile_asset(correction)
                if existing is not None:
                    existing_path = self._asset_path(existing.relative_path)
                    if existing_path.is_file():
                        return existing_path
                    await session.delete(existing)
                    await session.flush()
                os.replace(temporary_path, final_path)
                final_created = True
                session.add(
                    AudioAsset(
                        id=asset_id,
                        correction_transcript_id=transcript_id,
                        synthesis_profile=SYNTHESIS_PROFILE,
                        relative_path=relative_path,
                        byte_size=final_path.stat().st_size,
                    )
                )
            final_created = False
            return final_path
        except AppError:
            raise
        except (OSError, SQLAlchemyError, RuntimeError) as error:
            raise AppError("speech_generation_failed", "Audio generation failed.") from error
        finally:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)
            if final_created:
                with suppress(OSError):
                    final_path.unlink(missing_ok=True)

    async def _correction(
        self,
        session: AsyncSession,
        transcript_id: UUID,
    ) -> CorrectionResult | None:
        statement = (
            select(CorrectionResult)
            .where(CorrectionResult.transcript_id == transcript_id)
            .options(selectinload(CorrectionResult.audio_assets))
        )
        return (await session.scalars(statement)).one_or_none()

    @staticmethod
    async def _validate(
        session: AsyncSession,
        transcript_id: UUID,
        correction: CorrectionResult | None,
        expected_revision: int,
    ) -> None:
        if correction is None:
            if await session.get(Transcript, transcript_id) is None:
                raise AppError("not_found", "The transcript does not exist.")
            raise AppError("correction_unavailable", "A completed correction is required.")
        if correction.input_revision != expected_revision:
            raise AppError("revision_conflict", "The correction changed before synthesis.")

    @staticmethod
    def _profile_asset(correction: CorrectionResult | None) -> AudioAsset | None:
        if correction is None:
            return None
        return next(
            (
                asset
                for asset in correction.audio_assets
                if asset.synthesis_profile == SYNTHESIS_PROFILE
            ),
            None,
        )

    def _prepare_root(self) -> None:
        self.audio_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.audio_root.chmod(0o700)

    def _asset_path(self, relative_path: str) -> Path:
        candidate = (self.audio_root / relative_path).resolve()
        try:
            candidate.relative_to(self.audio_root.resolve())
        except ValueError as error:
            raise AppError("speech_unavailable", "Speech storage is unavailable.") from error
        return candidate
