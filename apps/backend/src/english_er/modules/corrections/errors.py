"""Provider failures safe to persist without raw model output."""

from enum import StrEnum


class ProviderErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    EXECUTION = "execution"
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    CONFIGURATION = "configuration"
    UNAVAILABLE_MODEL = "unavailable_model"


class ProviderError(Exception):
    def __init__(
        self,
        category: ProviderErrorCategory,
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


def timeout_error() -> ProviderError:
    return ProviderError(
        ProviderErrorCategory.TIMEOUT,
        "correction provider timed out",
        retryable=True,
    )


def invalid_output_error() -> ProviderError:
    return ProviderError(
        ProviderErrorCategory.INVALID_OUTPUT,
        "correction provider returned invalid structured output",
        retryable=True,
    )


def execution_error() -> ProviderError:
    return ProviderError(
        ProviderErrorCategory.EXECUTION,
        "correction provider execution failed",
        retryable=True,
    )
