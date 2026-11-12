"""Strict models that define the version-1 HTTP contract."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from english_er.config import MAX_TRANSCRIPT_CHARACTERS
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.shared.schema import ContractModel


class CorrectionPair(ContractModel):
    wrong: str = Field(min_length=1)
    correct: str = Field(min_length=1)


class CorrectionResult(ContractModel):
    corrected_text: str
    corrections: list[CorrectionPair]
    overall_observation: str
    audio_available: bool
    provider: str
    model: str
    prompt_version: str
    input_revision: int = Field(ge=1)
    created_at: datetime


class TranscriptSummary(ContractModel):
    id: UUID
    source: Literal["voxtype"]
    preview: str
    captured_at: datetime
    reviewed_at: datetime | None
    status: ProcessingStatus
    attempt_count: int = Field(ge=0)
    last_error: str | None


class PageMetadata(ContractModel):
    next_cursor: str | None


class TranscriptPage(ContractModel):
    items: list[TranscriptSummary]
    metadata: PageMetadata


class TranscriptDetail(TranscriptSummary):
    original_text: str
    transcript_text: str
    text_revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    correction: CorrectionResult | None


class ReviewUpdate(ContractModel):
    reviewed: bool


class TranscriptTextUpdate(ContractModel):
    text: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_CHARACTERS)
    expected_revision: int = Field(ge=1)

    @field_validator("text")
    @classmethod
    def require_non_whitespace_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("transcript text must not be blank")
        return value
