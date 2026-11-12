"""Create the initial persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_stage1"
down_revision: str | None = "0000_prior"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

processing_status = sa.Enum(
    "pending",
    "processing",
    "completed",
    "failed",
    name="processing_status",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", processing_status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="ck_transcripts_attempt_count_nonnegative"),
        sa.CheckConstraint("source = 'voxtype'", name="ck_transcripts_source_voxtype"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcripts_captured_at", "transcripts", ["captured_at"])
    op.create_index(
        "ix_transcripts_status_captured_at",
        "transcripts",
        ["status", "captured_at"],
    )
    op.create_table(
        "correction_results",
        sa.Column("transcript_id", sa.Uuid(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("corrections", sa.JSON(), nullable=False),
        sa.Column("overall_observation", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("transcript_id"),
    )


def downgrade() -> None:
    op.drop_table("correction_results")
    op.drop_index("ix_transcripts_status_captured_at", table_name="transcripts")
    op.drop_index("ix_transcripts_captured_at", table_name="transcripts")
    op.drop_table("transcripts")
