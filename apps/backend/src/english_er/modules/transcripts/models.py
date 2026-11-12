"""Transcript aggregate persistence model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from english_er.infra.orm import Base, UTCDateTime
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.shared.ids import uuid7
from english_er.shared.time import utc_now

processing_status_type = Enum(
    ProcessingStatus,
    name="processing_status",
    native_enum=False,
    create_constraint=False,
    values_callable=lambda members: [member.value for member in members],
)


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')", name="processing_status"
        ),
        CheckConstraint("source = 'voxtype'", name="ck_transcripts_source_voxtype"),
        CheckConstraint("attempt_count >= 0", name="ck_transcripts_attempt_count_nonnegative"),
        CheckConstraint("text_revision >= 1", name="ck_transcripts_text_revision_positive"),
        Index("ix_transcripts_status_queued_at", "status", "queued_at"),
        Index("ix_transcripts_captured_at", "captured_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    queued_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[ProcessingStatus] = mapped_column(
        processing_status_type,
        nullable=False,
        default=ProcessingStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now
    )

    correction: Mapped[CorrectionResult | None] = relationship(
        back_populates="transcript",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class CorrectionResult(Base):
    __tablename__ = "correction_results"
    __table_args__ = (
        CheckConstraint(
            "input_revision >= 1",
            name="ck_correction_results_input_revision_positive",
        ),
    )

    transcript_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrections: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    overall_observation: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    transcript: Mapped[Transcript] = relationship(back_populates="correction")
    audio_assets: Mapped[list[AudioAsset]] = relationship(
        back_populates="correction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AudioAsset(Base):
    __tablename__ = "audio_assets"
    __table_args__ = (
        UniqueConstraint(
            "correction_transcript_id",
            "synthesis_profile",
            name="uq_audio_assets_correction_profile",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7)
    correction_transcript_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("correction_results.transcript_id", ondelete="CASCADE"),
        nullable=False,
    )
    synthesis_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)

    correction: Mapped[CorrectionResult] = relationship(back_populates="audio_assets")
