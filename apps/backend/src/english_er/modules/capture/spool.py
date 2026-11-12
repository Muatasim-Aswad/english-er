"""Atomic, permission-restricted spool operations."""

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from english_er.modules.transcripts import CaptureEnvelope

DIRECTORY_MODE = 0o700
FILE_MODE = 0o600


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _enforce_directory(path: Path) -> None:
    path.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
    path.chmod(DIRECTORY_MODE)


@dataclass(frozen=True, slots=True)
class ClaimedCapture:
    path: Path
    envelope: CaptureEnvelope


class Spool:
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root
        self.root = state_root / "spool"
        self.pending = self.root / "pending"
        self.processing = self.root / "processing"
        self.failed = self.root / "failed"

    def ensure(self) -> None:
        for path in (self.state_root, self.root, self.pending, self.processing, self.failed):
            _enforce_directory(path)

    @staticmethod
    def _load(path: Path) -> CaptureEnvelope:
        with path.open("rb") as source:
            content = source.read(256_001)
        if len(content) > 256_000:
            raise ValueError("capture envelope is too large")
        return CaptureEnvelope.model_validate_json(content, strict=True)

    def _quarantine(self, path: Path) -> Path:
        source_directory = path.parent
        target = self.failed / path.name
        if target.exists():
            target = self.failed / f"{path.stem}.{uuid4().hex}{path.suffix}"
        os.replace(path, target)
        target.chmod(FILE_MODE)
        if source_directory != self.failed:
            _fsync_directory(source_directory)
        _fsync_directory(self.failed)
        return target

    def _claim_path(self, path: Path) -> Path | None:
        target = self.processing / path.name
        if target.exists():
            target = self.processing / f"{path.stem}.claim-{uuid4().hex}{path.suffix}"
        try:
            os.replace(path, target)
        except FileNotFoundError:
            return None
        target.chmod(FILE_MODE)
        _fsync_directory(self.pending)
        _fsync_directory(self.processing)
        return target

    def claim_oldest(self) -> ClaimedCapture | None:
        """Claim the oldest valid pending envelope and quarantine malformed entries."""

        self.ensure()
        valid: list[tuple[CaptureEnvelope, Path]] = []
        for path in sorted(self.pending.glob("*.json"), key=lambda candidate: candidate.name):
            if not path.is_file():
                continue
            try:
                envelope = self._load(path)
            except (OSError, UnicodeError, ValidationError, ValueError):
                claimed = self._claim_path(path)
                if claimed is not None:
                    self._quarantine(claimed)
                continue
            valid.append((envelope, path))

        valid.sort(key=lambda item: (item[0].captured_at, item[0].id.int, item[1].name))
        for _envelope, path in valid:
            claimed = self._claim_path(path)
            if claimed is None:
                continue
            try:
                envelope = self._load(claimed)
            except (OSError, UnicodeError, ValidationError, ValueError):
                self._quarantine(claimed)
                continue
            return ClaimedCapture(path=claimed, envelope=envelope)
        return None

    def recover_processing(self) -> int:
        """Return valid interrupted claims to pending and quarantine malformed files."""

        self.ensure()
        recovered = 0
        touched_processing = False
        for path in sorted(self.processing.glob("*.json"), key=lambda candidate: candidate.name):
            if not path.is_file():
                continue
            try:
                self._load(path)
            except (OSError, UnicodeError, ValidationError, ValueError):
                self._quarantine(path)
                touched_processing = True
                continue
            target = self.pending / path.name
            if target.exists():
                target = self.pending / f"{path.stem}.recovered-{uuid4().hex}{path.suffix}"
            os.replace(path, target)
            target.chmod(FILE_MODE)
            recovered += 1
            touched_processing = True
        if touched_processing:
            _fsync_directory(self.processing)
            _fsync_directory(self.pending)
        return recovered

    def quarantine(self, claim: ClaimedCapture) -> None:
        self._quarantine(claim.path)

    def complete(self, claim: ClaimedCapture) -> None:
        claim.path.unlink(missing_ok=True)
        _fsync_directory(self.processing)
