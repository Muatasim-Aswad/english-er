"""Strict version-1 spool envelope."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from english_er.config import MAX_TRANSCRIPT_CHARACTERS


class CaptureEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    id: UUID
    captured_at: datetime
    source: Literal["voxtype"]
    text: str = Field(max_length=MAX_TRANSCRIPT_CHARACTERS)

    @field_validator("id")
    @classmethod
    def require_uuid7(cls, value: UUID) -> UUID:
        if value.version != 7:
            raise ValueError("capture id must be UUIDv7")
        return value

    @field_validator("captured_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        offset = value.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("captured_at must be UTC")
        return value.astimezone(UTC)
