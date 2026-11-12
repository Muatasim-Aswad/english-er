"""Add editable, revisioned transcripts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_editable"
down_revision: str | None = "0001_stage1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("transcript_text", sa.Text(), nullable=True))
    op.add_column(
        "transcripts",
        sa.Column("text_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("transcripts", sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE transcripts SET transcript_text = original_text, queued_at = captured_at")

    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.alter_column("transcript_text", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column(
            "text_revision",
            existing_type=sa.Integer(),
            server_default=None,
        )
        batch_op.alter_column(
            "queued_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_transcripts_text_revision_positive",
            "text_revision >= 1",
        )

    op.drop_index("ix_transcripts_status_captured_at", table_name="transcripts")
    op.create_index(
        "ix_transcripts_status_queued_at",
        "transcripts",
        ["status", "queued_at"],
    )

    op.add_column(
        "correction_results",
        sa.Column("input_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    with op.batch_alter_table("correction_results") as batch_op:
        batch_op.alter_column(
            "input_revision",
            existing_type=sa.Integer(),
            server_default=None,
        )
        batch_op.create_check_constraint(
            "ck_correction_results_input_revision_positive",
            "input_revision >= 1",
        )


def downgrade() -> None:
    with op.batch_alter_table("correction_results") as batch_op:
        batch_op.drop_constraint(
            "ck_correction_results_input_revision_positive",
            type_="check",
        )
        batch_op.drop_column("input_revision")

    op.drop_index("ix_transcripts_status_queued_at", table_name="transcripts")
    op.create_index(
        "ix_transcripts_status_captured_at",
        "transcripts",
        ["status", "captured_at"],
    )

    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.drop_constraint("ck_transcripts_text_revision_positive", type_="check")
        batch_op.drop_column("queued_at")
        batch_op.drop_column("text_revision")
        batch_op.drop_column("transcript_text")
