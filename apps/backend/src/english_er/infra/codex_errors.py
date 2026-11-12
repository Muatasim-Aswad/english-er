"""Provider failures safe to persist without raw model output."""

from enum import StrEnum


class CodexErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    EXECUTION = "execution"
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    CONFIGURATION = "configuration"
    UNAVAILABLE_MODEL = "unavailable_model"


class CodexError(Exception):
    def __init__(
        self,
        category: CodexErrorCategory,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.public_message = message
        self.retryable = retryable

    @property
    def storage_message(self) -> str:
        return f"{self.category.value}: {self.public_message}"


def timeout_error() -> CodexError:
    return CodexError(
        CodexErrorCategory.TIMEOUT,
        "correction provider timed out",
        retryable=True,
    )


def invalid_output_error() -> CodexError:
    return CodexError(
        CodexErrorCategory.INVALID_OUTPUT,
        "correction provider returned invalid structured output",
        retryable=True,
    )


def execution_error() -> CodexError:
    return CodexError(
        CodexErrorCategory.EXECUTION,
        "correction provider execution failed",
        retryable=True,
    )


def classify_nonzero(stderr: bytes) -> CodexError:
    text = stderr.decode("utf-8", errors="ignore").casefold()
    if any(
        marker in text for marker in ("unauthorized", "authentication", "login required", "api key")
    ):
        return CodexError(
            CodexErrorCategory.AUTHENTICATION,
            "correction provider authentication failed",
            retryable=False,
        )
    if any(marker in text for marker in ("quota", "rate limit", "usage limit", "credits")):
        return CodexError(
            CodexErrorCategory.QUOTA,
            "correction provider quota is unavailable",
            retryable=False,
        )
    if any(
        marker in text
        for marker in (
            "model not found",
            "model does not exist",
            "model is unavailable",
            "unsupported model",
        )
    ):
        return CodexError(
            CodexErrorCategory.UNAVAILABLE_MODEL,
            "configured correction model is unavailable",
            retryable=False,
        )
    if any(
        marker in text
        for marker in ("configuration", "config error", "unknown option", "unrecognized option")
    ):
        return CodexError(
            CodexErrorCategory.CONFIGURATION,
            "correction provider configuration is invalid",
            retryable=False,
        )
    return execution_error()
