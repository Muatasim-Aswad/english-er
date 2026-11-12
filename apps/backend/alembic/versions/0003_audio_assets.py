"""Add correction-owned generated audio assets."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_audio_assets"
down_revision: str | None = "0002_editable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("correction_transcript_id", sa.Uuid(), nullable=False),
        sa.Column("synthesis_profile", sa.String(length=128), nullable=False),
        sa.Column("relative_path", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["correction_transcript_id"],
            ["correction_results.transcript_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path"),
        sa.UniqueConstraint(
            "correction_transcript_id",
            "synthesis_profile",
            name="uq_audio_assets_correction_profile",
        ),
    )


def downgrade() -> None:
    op.drop_table("audio_assets")
