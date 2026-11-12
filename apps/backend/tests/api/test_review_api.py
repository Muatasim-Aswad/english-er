"""End-to-end tests for the local review API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from english_er.entrypoints.http import create_app
from english_er.infra.database import Database, sqlite_url
from english_er.infra.orm import Base
from english_er.modules.transcripts.domain import ProcessingStatus
from english_er.modules.transcripts.models import AudioAsset, CorrectionResult, Transcript
from english_er.platform.resources import ApiRuntime

pytestmark = pytest.mark.anyio

FIRST_ID = UUID("0198f100-0000-7000-8000-000000000001")
SECOND_ID = UUID("0198f100-0000-7000-8000-000000000002")
THIRD_ID = UUID("0198f100-0000-7000-8000-000000000003")
FOURTH_ID = UUID("0198f100-0000-7000-8000-000000000004")
CAPTURED_AT = datetime(2026, 8, 30, 12, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@asynccontextmanager
async def api(
    tmp_path: Path,
    *,
    audio_root: Path | None = None,
    speech_timeout: float = 120,
    queue_timeout: float = 5,
) -> AsyncIterator[tuple[AsgiClient, Database, Path]]:
    database = Database.create(sqlite_url(tmp_path / "api.sqlite3"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    marker = tmp_path / "state" / "capture-enabled"
    synthesizer = FakeSynthesizer()
    app = create_app(
        runtime=ApiRuntime(
            database=database,
            capture_marker=marker,
            audio_root=audio_root or tmp_path / "audio",
            synthesizer=synthesizer,
            speech_timeout=speech_timeout,
            speech_queue_timeout=queue_timeout,
        )
    )
    app.state.fake_synthesizer = synthesizer
    yield AsgiClient(app), database, marker
    await database.close()


@dataclass(frozen=True, slots=True)
class AsgiResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]

    @property
    def text(self) -> str:
        return self.body.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.body)


class AsgiClient:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: object | None = None,
    ) -> AsgiResponse:
        body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
        headers = [(b"host", b"127.0.0.1")]
        if json_body is not None:
            headers.append((b"content-type", b"application/json"))
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": urlencode(params or {}).encode("ascii"),
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        }
        sent_request = False
        messages: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            nonlocal sent_request
            if sent_request:
                return {"type": "http.disconnect"}
            sent_request = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message: MutableMapping[str, Any]) -> None:
            messages.append(dict(message))

        await self.app(scope, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        response_body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        response_headers = {
            key.decode("latin-1"): value.decode("latin-1")
            for key, value in start.get("headers", [])
        }
        return AsgiResponse(
            status_code=int(start["status"]),
            body=response_body,
            headers=response_headers,
        )

    async def get(self, path: str, *, params: dict[str, object] | None = None) -> AsgiResponse:
        return await self.request("GET", path, params=params)

    async def put(self, path: str, *, json: object) -> AsgiResponse:
        return await self.request("PUT", path, json_body=json)

    async def post(self, path: str, *, json: object | None = None) -> AsgiResponse:
        return await self.request("POST", path, json_body=json)

    async def delete(self, path: str) -> AsgiResponse:
        return await self.request("DELETE", path)


@dataclass(slots=True)
class FakeSynthesizer:
    calls: int = 0

    async def synthesize(self, _text: str, target: Path) -> None:
        self.calls += 1
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(b"RIFFfake-wave")

    async def close(self) -> None:
        return None


def transcript(
    transcript_id: UUID,
    *,
    captured_at: datetime = CAPTURED_AT,
    status: ProcessingStatus = ProcessingStatus.COMPLETED,
    reviewed_at: datetime | None = None,
    attempt_count: int = 1,
) -> Transcript:
    return Transcript(
        id=transcript_id,
        source="voxtype",
        original_text=f"Transcript {transcript_id} " + "x" * 180,
        transcript_text=f"Transcript {transcript_id} " + "x" * 180,
        text_revision=1,
        captured_at=captured_at,
        queued_at=captured_at,
        reviewed_at=reviewed_at,
        status=status,
        attempt_count=attempt_count,
        last_error="timeout: correction provider timed out"
        if status == ProcessingStatus.FAILED
        else None,
        created_at=captured_at,
        updated_at=captured_at,
    )


def correction(transcript_id: UUID) -> CorrectionResult:
    return CorrectionResult(
        transcript_id=transcript_id,
        corrected_text="Corrected transcript.",
        corrections=[{"wrong": "Transcript", "correct": "Corrected transcript"}],
        overall_observation="One concise observation.",
        provider="codex",
        model="gpt-5.6-luna",
        prompt_version="correction-v1",
        input_revision=1,
        created_at=CAPTURED_AT,
    )


async def add(database: Database, *records: object) -> None:
    async with database.sessions.begin() as session:
        session.add_all(records)


def test_construction_and_openapi_do_not_touch_runtime_paths(tmp_path: Path) -> None:
    database_path = tmp_path / "missing-data" / "api.sqlite3"
    marker = tmp_path / "missing-state" / "capture-enabled"

    app = create_app(database_path=database_path, capture_marker=marker)
    schema = app.openapi()

    assert schema["paths"]["/api/v1/health"]
    assert not database_path.parent.exists()
    assert not marker.parent.exists()


async def test_health_and_atomic_capture_marker_control(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, _database, marker):
        assert (await client.get("/api/v1/health")).json() == {
            "api": "ok",
            "database": "ok",
        }
        assert (await client.get("/api/v1/capture")).json() == {"enabled": False}

        enabled = await client.put("/api/v1/capture", json={"enabled": True})
        assert enabled.json() == {"enabled": True}
        assert marker.stat().st_mode & 0o777 == 0o600
        assert marker.parent.stat().st_mode & 0o777 == 0o700
        assert (await client.put("/api/v1/capture", json={"enabled": True})).status_code == 200

        disabled = await client.put("/api/v1/capture", json={"enabled": False})
        assert disabled.json() == {"enabled": False}
        assert not marker.exists()


async def test_corrected_audio_is_generated_once_and_reused(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))

        before = await client.get(f"/api/v1/transcripts/{FIRST_ID}")
        assert before.json()["correction"]["audio_available"] is False

        first = await client.post(
            f"/api/v1/transcripts/{FIRST_ID}/audio",
            json={"expected_revision": 1},
        )
        second = await client.post(
            f"/api/v1/transcripts/{FIRST_ID}/audio",
            json={"expected_revision": 1},
        )

        assert first.status_code == 200
        assert first.headers["content-type"] == "audio/wav"
        assert first.body == b"RIFFfake-wave"
        assert second.body == first.body
        assert client.app.state.fake_synthesizer.calls == 1
        after = await client.get(f"/api/v1/transcripts/{FIRST_ID}")
        assert after.json()["correction"]["audio_available"] is True
        async with database.sessions() as session:
            asset = (await session.scalars(select(AudioAsset))).one()
        assert asset.id.version == 7
        assert asset.correction_transcript_id == FIRST_ID
        assert (tmp_path / "audio" / asset.relative_path).read_bytes() == first.body


async def test_corrected_audio_reports_unavailable_storage(tmp_path: Path) -> None:
    blocked_root = tmp_path / "blocked-audio-root"
    blocked_root.write_text("not a directory", encoding="utf-8")
    async with api(tmp_path, audio_root=blocked_root) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))

        response = await client.post(
            f"/api/v1/transcripts/{FIRST_ID}/audio",
            json={"expected_revision": 1},
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "speech_generation_failed"
        assert response.json()["error"]["message"] == "Audio generation failed."
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
        assert client.app.state.fake_synthesizer.calls == 0


async def test_corrected_audio_rejects_stale_or_missing_correction(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))
        await add(database, transcript(SECOND_ID, status=ProcessingStatus.PENDING))

        stale = await client.post(
            f"/api/v1/transcripts/{FIRST_ID}/audio",
            json={"expected_revision": 2},
        )
        missing = await client.post(
            f"/api/v1/transcripts/{SECOND_ID}/audio",
            json={"expected_revision": 1},
        )

        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "revision_conflict"
        assert missing.status_code == 409
        assert missing.json()["error"]["code"] == "correction_unavailable"


async def test_list_filters_and_stable_cursor_traversal(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(
            database,
            transcript(FIRST_ID, captured_at=CAPTURED_AT + timedelta(minutes=1)),
            transcript(SECOND_ID),
            transcript(THIRD_ID),
            transcript(
                FOURTH_ID,
                captured_at=CAPTURED_AT - timedelta(minutes=1),
                status=ProcessingStatus.FAILED,
                reviewed_at=CAPTURED_AT,
            ),
        )

        first_page = (await client.get("/api/v1/transcripts", params={"limit": 2})).json()
        second_page = (
            await client.get(
                "/api/v1/transcripts",
                params={"limit": 2, "cursor": first_page["metadata"]["next_cursor"]},
            )
        ).json()
        first_ids = [item["id"] for item in first_page["items"]]
        second_ids = [item["id"] for item in second_page["items"]]
        assert first_ids == [str(FIRST_ID), str(THIRD_ID)]
        assert second_ids == [str(SECOND_ID), str(FOURTH_ID)]
        assert set(first_ids).isdisjoint(second_ids)
        assert second_page["metadata"]["next_cursor"] is None
        assert len(first_page["items"][0]["preview"]) == 160

        combined = (
            await client.get(
                "/api/v1/transcripts",
                params={"status": "completed", "reviewed": "unreviewed"},
            )
        ).json()
        assert {item["id"] for item in combined["items"]} == {
            str(FIRST_ID),
            str(SECOND_ID),
            str(THIRD_ID),
        }


async def test_detail_and_review_updates_are_idempotent(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))

        detail = (await client.get(f"/api/v1/transcripts/{FIRST_ID}")).json()
        assert detail["original_text"].startswith("Transcript")
        assert detail["transcript_text"] == detail["original_text"]
        assert detail["text_revision"] == 1
        assert detail["correction"]["corrected_text"] == "Corrected transcript."
        assert detail["correction"]["input_revision"] == 1

        reviewed = (
            await client.put(f"/api/v1/transcripts/{FIRST_ID}/review", json={"reviewed": True})
        ).json()
        reviewed_again = (
            await client.put(f"/api/v1/transcripts/{FIRST_ID}/review", json={"reviewed": True})
        ).json()
        assert reviewed["reviewed_at"] == reviewed_again["reviewed_at"]

        unreviewed = (
            await client.put(f"/api/v1/transcripts/{FIRST_ID}/review", json={"reviewed": False})
        ).json()
        assert unreviewed["reviewed_at"] is None


async def test_text_edit_requeues_and_replaces_the_current_correction(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        reviewed_at = CAPTURED_AT + timedelta(minutes=1)
        await add(
            database,
            transcript(FIRST_ID, reviewed_at=reviewed_at),
            correction(FIRST_ID),
        )
        generated = await client.post(
            f"/api/v1/transcripts/{FIRST_ID}/audio",
            json={"expected_revision": 1},
        )
        assert generated.status_code == 200
        async with database.sessions() as session:
            old_asset = (await session.scalars(select(AudioAsset))).one()
        old_audio = tmp_path / "audio" / old_asset.relative_path
        assert old_audio.is_file()

        response = await client.put(
            f"/api/v1/transcripts/{FIRST_ID}/text",
            json={"text": "Manually repaired transcript.", "expected_revision": 1},
        )

        assert response.status_code == 200
        detail = response.json()
        assert detail["original_text"].startswith("Transcript")
        assert detail["transcript_text"] == "Manually repaired transcript."
        assert detail["text_revision"] == 2
        assert detail["status"] == "pending"
        assert detail["attempt_count"] == 0
        assert detail["last_error"] is None
        assert detail["reviewed_at"] is None
        assert detail["correction"] is None

        page = (await client.get("/api/v1/transcripts")).json()
        assert page["items"][0]["preview"] == "Manually repaired transcript."
        async with database.sessions() as session:
            stored = await session.get(CorrectionResult, FIRST_ID)
            audio_count = await session.scalar(select(func.count()).select_from(AudioAsset))
        assert stored is None
        assert audio_count == 0
        assert not old_audio.exists()


async def test_text_edit_is_idempotent_and_rejects_stale_revision(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))
        current_text = f"Transcript {FIRST_ID} " + "x" * 180

        unchanged = await client.put(
            f"/api/v1/transcripts/{FIRST_ID}/text",
            json={"text": current_text, "expected_revision": 1},
        )
        assert unchanged.status_code == 200
        assert unchanged.json()["status"] == "completed"
        assert unchanged.json()["text_revision"] == 1
        assert unchanged.json()["correction"] is not None

        changed = await client.put(
            f"/api/v1/transcripts/{FIRST_ID}/text",
            json={"text": "A newer transcript.", "expected_revision": 1},
        )
        assert changed.status_code == 200
        conflict = await client.put(
            f"/api/v1/transcripts/{FIRST_ID}/text",
            json={"text": "A stale overwrite.", "expected_revision": 1},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "revision_conflict"


async def test_retry_conflict_delete_and_not_found(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(
            database,
            transcript(FIRST_ID, status=ProcessingStatus.FAILED, attempt_count=2),
            transcript(SECOND_ID),
            correction(SECOND_ID),
        )

        retried = (await client.post(f"/api/v1/transcripts/{FIRST_ID}/retry")).json()
        assert retried["status"] == "pending"
        assert retried["attempt_count"] == 0
        assert retried["last_error"] is None
        assert (await client.post(f"/api/v1/transcripts/{SECOND_ID}/retry")).status_code == 409
        assert (await client.post(f"/api/v1/transcripts/{THIRD_ID}/retry")).status_code == 404

        assert (await client.delete(f"/api/v1/transcripts/{SECOND_ID}")).status_code == 204
        assert (await client.get(f"/api/v1/transcripts/{SECOND_ID}")).status_code == 404
        async with database.sessions() as session:
            count = await session.scalar(select(func.count()).select_from(CorrectionResult))
        assert count == 0


async def test_validation_errors_are_explicit_and_privacy_safe(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, _database, _marker):
        for response in (
            await client.get("/api/v1/transcripts/not-a-uuid"),
            await client.get("/api/v1/transcripts", params={"limit": 0}),
            await client.get("/api/v1/transcripts", params={"cursor": "not a cursor"}),
            await client.put("/api/v1/capture", json={"enabled": "yes"}),
            await client.put(
                f"/api/v1/transcripts/{FIRST_ID}/text",
                json={"text": "   ", "expected_revision": 1},
            ),
        ):
            assert response.status_code == 422
            assert set(response.json()) == {"error"}
            assert response.json()["error"]["status"] == 422
            assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
            assert "not a cursor" not in response.text


async def test_database_and_marker_failures_are_bounded(tmp_path: Path) -> None:
    broken_database = Database.create(sqlite_url(tmp_path / "missing" / "api.sqlite3"))
    marker_parent = tmp_path / "marker-parent"
    marker_parent.write_text("not a directory", encoding="utf-8")
    app = create_app(
        runtime=ApiRuntime(
            database=broken_database,
            capture_marker=marker_parent / "capture-enabled",
        )
    )
    client = AsgiClient(app)
    health = await client.get("/api/v1/health")
    assert health.json() == {"api": "ok", "database": "unavailable"}
    unavailable = await client.get("/api/v1/transcripts")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "database_unavailable"
    capture = await client.put("/api/v1/capture", json={"enabled": True})
    assert capture.status_code == 503
    assert capture.json()["error"]["code"] == "capture_unavailable"
    assert str(tmp_path) not in capture.text
    await broken_database.close()


async def test_spa_fallback_never_swallows_api_routes(tmp_path: Path) -> None:
    static_root = tmp_path / "dist"
    static_root.mkdir()
    (static_root / "index.html").write_text("<main>English-er</main>", encoding="utf-8")
    database = Database.create(sqlite_url(tmp_path / "api.sqlite3"))
    app = create_app(
        runtime=ApiRuntime(database=database, capture_marker=tmp_path / "capture-enabled"),
        static_root=static_root,
    )
    client = AsgiClient(app)
    assert "English-er" in (await client.get("/review/anything")).text
    api_missing = await client.get("/api/v1/not-a-route")
    assert api_missing.status_code == 404
    assert "English-er" not in api_missing.text
    await database.close()


async def test_simultaneous_edits_check_revision_in_the_write_transaction(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))
        responses = await asyncio.gather(
            *(
                client.put(
                    f"/api/v1/transcripts/{FIRST_ID}/text",
                    json={"text": text, "expected_revision": 1},
                )
                for text in ("First concurrent edit.", "Second concurrent edit.")
            )
        )
        assert sorted(response.status_code for response in responses) == [200, 409]
        conflict = next(response for response in responses if response.status_code == 409)
        assert conflict.json()["error"]["details"] == {"current_revision": 2}
        current = (await client.get(f"/api/v1/transcripts/{FIRST_ID}")).json()
        assert current["text_revision"] == 2
        assert current["transcript_text"] in {"First concurrent edit.", "Second concurrent edit."}


async def test_cursor_cannot_be_reused_with_different_filters(tmp_path: Path) -> None:
    async with api(tmp_path) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), transcript(SECOND_ID))
        page = (await client.get("/api/v1/transcripts", params={"limit": 1})).json()
        response = await client.get(
            "/api/v1/transcripts",
            params={"cursor": page["metadata"]["next_cursor"], "status": "failed"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_cursor"


async def test_speech_timeout_releases_admission_and_leaves_no_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def blocked(_self: FakeSynthesizer, _text: str, _target: Path) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSynthesizer, "synthesize", blocked)
    async with api(tmp_path, speech_timeout=0.01) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))
        for _ in range(2):
            response = await client.post(
                f"/api/v1/transcripts/{FIRST_ID}/audio", json={"expected_revision": 1}
            )
            assert response.status_code == 504
            assert response.json()["error"]["code"] == "speech_timeout"
        async with database.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(AudioAsset)) == 0
        assert not list((tmp_path / "audio").glob("*"))


async def test_speech_queue_has_a_deadline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked(_self: FakeSynthesizer, _text: str, target: Path) -> None:
        entered.set()
        await release.wait()
        target.write_bytes(b"RIFFfake-wave")

    monkeypatch.setattr(FakeSynthesizer, "synthesize", blocked)
    async with api(tmp_path, queue_timeout=0.01) as (client, database, _marker):
        await add(database, transcript(FIRST_ID), correction(FIRST_ID))
        first = asyncio.create_task(
            client.post(f"/api/v1/transcripts/{FIRST_ID}/audio", json={"expected_revision": 1})
        )
        await entered.wait()
        try:
            second = await client.post(
                f"/api/v1/transcripts/{FIRST_ID}/audio", json={"expected_revision": 1}
            )
            assert second.status_code == 503
            assert second.json()["error"]["code"] == "busy"
        finally:
            release.set()
            assert (await first).status_code == 200
