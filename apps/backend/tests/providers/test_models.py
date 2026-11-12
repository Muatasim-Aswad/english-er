"""Strict correction result validation."""

import json

import pytest
from pydantic import ValidationError

from english_er.modules.transcripts.result import Correction


def valid_payload() -> dict[str, object]:
    return {
        "corrected_text": "I went home.",
        "corrections": [{"wrong": "go", "correct": "went"}],
        "overall_observation": "Past tense was corrected.",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"extra": "rejected"},
        {"corrected_text": ""},
        {"corrected_text": "   "},
        {"corrections": [{"wrong": "go", "correct": "go"}]},
        {"corrections": [{"wrong": "", "correct": "went"}]},
    ],
)
def test_strict_validation_rejects_invalid_fields(change: dict[str, object]) -> None:
    payload = valid_payload() | change
    with pytest.raises(ValidationError):
        Correction.model_validate_json(json.dumps(payload), strict=True)


def test_strict_validation_rejects_missing_corrected_text() -> None:
    payload = valid_payload()
    del payload["corrected_text"]
    with pytest.raises(ValidationError):
        Correction.model_validate(payload, strict=True)


def test_wrong_value_must_appear_in_original() -> None:
    correction = Correction.model_validate(valid_payload(), strict=True)
    with pytest.raises(ValueError, match="absent"):
        correction.validate_against("I walked home.")
