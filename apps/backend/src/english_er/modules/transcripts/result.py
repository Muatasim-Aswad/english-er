"""Strict provider result models and the replaceable provider protocol."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class CorrectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    wrong: str
    correct: str

    @field_validator("wrong", "correct")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("correction text must not be empty")
        return value

    @model_validator(mode="after")
    def require_change(self) -> CorrectionItem:
        if self.wrong == self.correct:
            raise ValueError("wrong and correct must differ")
        return self


class Correction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    corrected_text: str
    corrections: list[CorrectionItem]
    overall_observation: str

    @field_validator("corrected_text", "overall_observation")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be empty")
        return value

    def validate_against(self, transcript: str) -> None:
        for item in self.corrections:
            if item.wrong not in transcript:
                raise ValueError("a wrong value is absent from the transcript")


class CorrectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    correction: Correction
    provider: str
    model: str
    prompt_version: str

    @field_validator("provider", "model", "prompt_version")
    @classmethod
    def require_metadata(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("provider metadata must not be empty")
        return value
