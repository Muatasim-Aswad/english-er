import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from english_er.config import Settings
from english_er.infra.database import Database
from english_er.shared.speech import SpeechSynthesizer


@dataclass(frozen=True, slots=True)
class ApiRuntime:
    database: Database
    capture_marker: Path
    audio_root: Path = field(default_factory=lambda: Settings().audio_root)
    synthesizer: SpeechSynthesizer | None = None
    audio_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    speech_timeout: float = 120
    speech_queue_timeout: float = 5
