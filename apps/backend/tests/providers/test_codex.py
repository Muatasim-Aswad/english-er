"""Fresh-process Codex adapter behavior."""

import json
from pathlib import Path

import pytest

from english_er.infra.codex import CODEX_MODEL
from english_er.modules.corrections.errors import ProviderError, ProviderErrorCategory
from english_er.modules.corrections.provider import CodexCorrectionProvider


def make_executable(tmp_path: Path, body: str) -> Path:
    executable = tmp_path / "fake-codex"
    executable.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    executable.chmod(0o700)
    return executable


@pytest.mark.asyncio
async def test_success_uses_isolated_ephemeral_command_and_final_message(tmp_path: Path) -> None:
    observation = tmp_path / "observation.json"
    body = f"""
import json
import os
import pathlib
import sys
args = sys.argv[1:]
result = pathlib.Path(args[args.index('--output-last-message') + 1])
schema = pathlib.Path(args[args.index('--output-schema') + 1])
stdin = sys.stdin.read()
pathlib.Path({str(observation)!r}).write_text(json.dumps({{
    'args': args,
    'cwd_entries': os.listdir('.'),
    'stdin': stdin,
    'schema': json.loads(schema.read_text()),
}}))
result.write_text(json.dumps({{
    'corrected_text': 'I went home.',
    'corrections': [{{'wrong': 'go', 'correct': 'went'}}],
    'overall_observation': 'Past tense was corrected.',
}}))
"""
    provider = CodexCorrectionProvider(executable=str(make_executable(tmp_path, body)))

    result = await provider.correct("I go home.")

    recorded = json.loads(observation.read_text(encoding="utf-8"))
    args = recorded["args"]
    assert args[0] == "exec"
    assert recorded["cwd_entries"] == []
    assert recorded["schema"]["additionalProperties"] is False
    assert "<english-er-transcript>" in recorded["stdin"]
    assert "I go home." in recorded["stdin"]
    for expected in (
        "--skip-git-repo-check",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--output-schema",
        "--output-last-message",
    ):
        assert expected in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert args[args.index("--model") + 1] == CODEX_MODEL
    assert args[args.index("-c") + 1] == 'model_reasoning_effort="low"'
    assert result.correction.corrected_text == "I went home."


@pytest.mark.asyncio
async def test_timeout_terminates_child(tmp_path: Path) -> None:
    terminated = tmp_path / "terminated"
    body = f"""
import pathlib
import signal
import time
def terminate(_signum, _frame):
    pathlib.Path({str(terminated)!r}).write_text('terminated')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, terminate)
time.sleep(30)
"""
    provider = CodexCorrectionProvider(
        executable=str(make_executable(tmp_path, body)),
        timeout_seconds=0.2,
    )

    with pytest.raises(ProviderError) as captured:
        await provider.correct("text")

    assert captured.value.category == ProviderErrorCategory.TIMEOUT
    assert captured.value.retryable is True
    assert terminated.read_text(encoding="utf-8") == "terminated"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output", "category"),
    [
        ("not-json", ProviderErrorCategory.INVALID_OUTPUT),
        (
            json.dumps(
                {
                    "corrected_text": "Fixed",
                    "corrections": [],
                    "overall_observation": "Fine",
                    "extra": "forbidden",
                }
            ),
            ProviderErrorCategory.INVALID_OUTPUT,
        ),
        (
            json.dumps(
                {
                    "corrected_text": "Fixed",
                    "corrections": [{"wrong": "missing", "correct": "Fixed"}],
                    "overall_observation": "Fine",
                }
            ),
            ProviderErrorCategory.INVALID_OUTPUT,
        ),
    ],
)
async def test_invalid_final_output_is_rejected(
    tmp_path: Path,
    output: str,
    category: ProviderErrorCategory,
) -> None:
    body = f"""
import pathlib
import sys
args = sys.argv[1:]
pathlib.Path(args[args.index('--output-last-message') + 1]).write_text({output!r})
"""
    provider = CodexCorrectionProvider(executable=str(make_executable(tmp_path, body)))
    with pytest.raises(ProviderError) as captured:
        await provider.correct("original")
    assert captured.value.category == category


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stderr", "category", "retryable"),
    [
        ("authentication required", ProviderErrorCategory.AUTHENTICATION, False),
        ("quota exceeded", ProviderErrorCategory.QUOTA, False),
        ("configuration error", ProviderErrorCategory.CONFIGURATION, False),
        ("model is unavailable", ProviderErrorCategory.UNAVAILABLE_MODEL, False),
        ("temporary child failure", ProviderErrorCategory.EXECUTION, True),
    ],
)
async def test_nonzero_exit_is_categorized_without_validating_output(
    tmp_path: Path,
    stderr: str,
    category: ProviderErrorCategory,
    retryable: bool,
) -> None:
    body = f"""
import pathlib
import sys
args = sys.argv[1:]
pathlib.Path(args[args.index('--output-last-message') + 1]).write_text('{{}}')
sys.stderr.write({stderr!r})
raise SystemExit(2)
"""
    provider = CodexCorrectionProvider(executable=str(make_executable(tmp_path, body)))
    with pytest.raises(ProviderError) as captured:
        await provider.correct("original")
    assert captured.value.category == category
    assert captured.value.retryable is retryable
