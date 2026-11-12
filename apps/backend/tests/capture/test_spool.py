from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from english_er.modules.capture.spool import Spool
from english_er.shared.ids import uuid7


def write_envelope(path: Path, *, captured_at: datetime, text: str = "text") -> UUID:
    capture_id = uuid7()
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "id": str(capture_id),
                "captured_at": captured_at.isoformat().replace("+00:00", "Z"),
                "source": "voxtype",
                "text": text,
            }
        )
    )
    return capture_id


def test_claims_by_envelope_time_and_ignores_partial_files(tmp_path: Path) -> None:
    spool = Spool(tmp_path / "state")
    spool.ensure()
    now = datetime.now(UTC)
    newer_id = write_envelope(spool.pending / "a.json", captured_at=now, text="newer")
    older_id = write_envelope(
        spool.pending / "z.json",
        captured_at=now - timedelta(minutes=1),
        text="older",
    )
    (spool.pending / ".partial.tmp").write_text("partial")

    first = spool.claim_oldest()
    second = spool.claim_oldest()

    assert first is not None and first.envelope.id == older_id
    assert second is not None and second.envelope.id == newer_id
    assert (spool.pending / ".partial.tmp").exists()
    assert first.path.parent == spool.processing


def test_quarantines_malformed_and_wrong_version_envelopes(tmp_path: Path) -> None:
    spool = Spool(tmp_path / "state")
    spool.ensure()
    (spool.pending / "broken.json").write_text("not-json")
    (spool.pending / "wrong-version.json").write_text(
        json.dumps(
            {
                "version": 2,
                "id": str(uuid7()),
                "captured_at": datetime.now(UTC).isoformat(),
                "source": "voxtype",
                "text": "hidden",
            }
        )
    )

    assert spool.claim_oldest() is None
    assert len(list(spool.failed.glob("*.json"))) == 2
    assert not list(spool.processing.iterdir())


def test_restart_recovers_valid_processing_and_quarantines_invalid(tmp_path: Path) -> None:
    spool = Spool(tmp_path / "state")
    spool.ensure()
    capture_id = write_envelope(spool.processing / "valid.json", captured_at=datetime.now(UTC))
    (spool.processing / "invalid.json").write_text("{}")

    assert spool.recover_processing() == 1
    assert not list(spool.processing.iterdir())
    claim = spool.claim_oldest()
    assert claim is not None and claim.envelope.id == capture_id
    assert len(list(spool.failed.glob("*.json"))) == 1


def test_complete_deletes_only_the_claim(tmp_path: Path) -> None:
    spool = Spool(tmp_path / "state")
    spool.ensure()
    write_envelope(spool.pending / "capture.json", captured_at=datetime.now(UTC))
    claim = spool.claim_oldest()
    assert claim is not None

    spool.complete(claim)

    assert not claim.path.exists()
