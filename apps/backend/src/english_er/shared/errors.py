"""Transport-independent failures; only public fields may reach a caller."""

from typing import Literal

Code = Literal[
    "not_ready",
    "not_found",
    "validation_error",
    "invalid_cursor",
    "revision_conflict",
    "invalid_state",
    "database_unavailable",
    "capture_unavailable",
    "capture_conflict",
    "speech_unavailable",
    "correction_unavailable",
    "speech_generation_failed",
    "speech_timeout",
    "busy",
    "invalid_host",
    "invalid_origin",
    "request_too_large",
    "request_timeout",
    "rate_limited",
    "internal_error",
]


class AppError(Exception):
    def __init__(
        self, code: Code, message: str, *, public: dict[str, str | int] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.public = public
