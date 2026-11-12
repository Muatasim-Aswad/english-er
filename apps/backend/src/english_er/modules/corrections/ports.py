from typing import Protocol

from english_er.modules.transcripts import ProviderResult as CorrectionResult


class CorrectionProvider(Protocol):
    async def correct(self, transcript: str) -> CorrectionResult: ...
