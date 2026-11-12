"""Map the Codex subprocess contract into the correction domain."""

from pydantic import ValidationError

from english_er.infra.codex import CODEX_MODEL, CodexProcess, ProcessFactory
from english_er.infra.codex_errors import CodexError
from english_er.modules.corrections.errors import (
    ProviderError,
    ProviderErrorCategory,
    invalid_output_error,
)
from english_er.modules.corrections.prompt import PROMPT_VERSION, build_prompt
from english_er.modules.transcripts import Correction
from english_er.modules.transcripts import ProviderResult as CorrectionResult


class CodexCorrectionProvider:
    provider_name = "codex"

    def __init__(
        self,
        *,
        executable: str = "codex",
        timeout_seconds: float = 120,
        process_factory: ProcessFactory | None = None,
    ) -> None:
        options = {} if process_factory is None else {"process_factory": process_factory}
        self.process = CodexProcess(
            executable=executable, timeout_seconds=timeout_seconds, **options
        )

    async def correct(self, transcript: str) -> CorrectionResult:
        try:
            raw = await self.process.execute(
                build_prompt(transcript), Correction.model_json_schema()
            )
        except CodexError as error:
            raise ProviderError(
                ProviderErrorCategory(error.category.value),
                error.public_message,
                retryable=error.retryable,
            ) from error
        try:
            correction = Correction.model_validate_json(raw, strict=True)
            correction.validate_against(transcript)
        except (ValueError, ValidationError) as error:
            raise invalid_output_error() from error
        return CorrectionResult(
            correction=correction,
            provider=self.provider_name,
            model=CODEX_MODEL,
            prompt_version=PROMPT_VERSION,
        )
