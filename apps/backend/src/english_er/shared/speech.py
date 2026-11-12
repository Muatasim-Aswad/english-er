from pathlib import Path
from typing import Protocol


class SpeechSynthesizer(Protocol):
    async def synthesize(self, text: str, target: Path) -> None: ...
    async def close(self) -> None: ...
