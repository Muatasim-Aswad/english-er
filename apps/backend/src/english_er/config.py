"""Validated startup settings and protocol limits."""

import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MAX_TRANSCRIPT_CHARACTERS = 32_000
SAMPLE_RATE = 24_000
VOICE = "af_heart"
SYNTHESIS_PROFILE = "kokoro-82m:af_heart:pcm16-24khz:v1"


def xdg_path(name: str, fallback: str) -> Path:
    return Path(os.environ.get(name, str(Path.home() / fallback))).expanduser().resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENGLISH_ER_", frozen=True, extra="forbid")

    database_path: Path = Field(
        default_factory=lambda: (
            xdg_path("XDG_DATA_HOME", ".local/share") / "english-er/english-er.sqlite3"
        )
    )
    database_url: str | None = None
    state_root: Path = Field(
        default_factory=lambda: xdg_path("XDG_STATE_HOME", ".local/state") / "english-er"
    )
    audio_root: Path = Field(
        default_factory=lambda: xdg_path("XDG_CACHE_HOME", ".cache") / "english-er/tts"
    )
    codex_executable: str = "codex"
    provider_timeout: float = Field(default=120, gt=0, le=600)
    speech_timeout: float = Field(default=120, gt=0, le=600)
    speech_queue_timeout: float = Field(default=5, gt=0, le=30)
    request_timeout: float = Field(default=150, gt=0, le=660)
    max_body_bytes: int = Field(default=256_000, gt=0, le=1_000_000)
    max_concurrent_requests: int = Field(default=16, gt=0, le=64)
    requests_per_minute: int = Field(default=600, gt=0)
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8765",
    )

    @property
    def capture_marker(self) -> Path:
        return self.state_root / "capture-enabled"

    @field_validator("database_url")
    @classmethod
    def require_sqlite_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("sqlite+aiosqlite:///"):
            raise ValueError("only sqlite+aiosqlite database URLs are supported")
        return value
