from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
PRIOR_FIXTURE = Path(__file__).with_name("fixtures") / "prior_revision.sql"


def upgrade(database_path: Path) -> None:
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")
    command.upgrade(config, "head")


def schema(
    database_path: Path,
) -> tuple[set[str], set[str], list[tuple[object, ...]], list[tuple[object, ...]]]:
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'alembic_version'"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
            )
        }
        foreign_keys = list(connection.execute("PRAGMA foreign_key_list(correction_results)"))
        audio_foreign_keys = list(connection.execute("PRAGMA foreign_key_list(audio_assets)"))
    return tables, indexes, foreign_keys, audio_foreign_keys


def test_fresh_and_prior_revision_upgrades_reach_same_schema(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.sqlite3"
    prior = tmp_path / "prior.sqlite3"
    with sqlite3.connect(prior) as connection:
        connection.executescript(PRIOR_FIXTURE.read_text())

    upgrade(fresh)
    upgrade(prior)

    fresh_schema = schema(fresh)
    assert schema(prior) == fresh_schema
    tables, indexes, foreign_keys, audio_foreign_keys = fresh_schema
    assert tables == {"transcripts", "correction_results", "audio_assets"}
    assert indexes == {"ix_transcripts_captured_at", "ix_transcripts_status_queued_at"}
    assert len(foreign_keys) == 1
    assert foreign_keys[0][2] == "transcripts"
    assert foreign_keys[0][6] == "CASCADE"
    assert len(audio_foreign_keys) == 1
    assert audio_foreign_keys[0][2] == "correction_results"
    assert audio_foreign_keys[0][6] == "CASCADE"


def test_schema_contains_required_columns_and_head_revision(tmp_path: Path) -> None:
    database = tmp_path / "schema.sqlite3"
    upgrade(database)
    with sqlite3.connect(database) as connection:
        transcript_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(transcripts)")
        }
        correction_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(correction_results)")
        }
        audio_columns = {row[1] for row in connection.execute("PRAGMA table_info(audio_assets)")}
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    assert transcript_columns == {
        "id",
        "source",
        "original_text",
        "transcript_text",
        "text_revision",
        "captured_at",
        "queued_at",
        "reviewed_at",
        "status",
        "attempt_count",
        "last_error",
        "created_at",
        "updated_at",
    }
    assert correction_columns == {
        "transcript_id",
        "corrected_text",
        "corrections",
        "overall_observation",
        "provider",
        "model",
        "prompt_version",
        "input_revision",
        "created_at",
    }
    assert audio_columns == {
        "id",
        "correction_transcript_id",
        "synthesis_profile",
        "relative_path",
        "byte_size",
        "created_at",
    }
    assert revision == ("0003_audio_assets",)


def test_migration_head_matches_the_registered_aggregate_metadata(tmp_path: Path) -> None:
    database = tmp_path / "metadata.sqlite3"
    upgrade(database)
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    command.check(config)
