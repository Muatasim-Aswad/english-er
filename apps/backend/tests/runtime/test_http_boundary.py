import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message

from english_er.config import Settings
from english_er.entrypoints.http import create_app
from english_er.platform.http import LocalHttpBoundary


def settings(tmp_path: Path, **overrides: Any) -> Settings:
    return Settings(
        database_path=tmp_path / "data/db.sqlite3",
        state_root=tmp_path / "state",
        audio_root=tmp_path / "audio",
        **overrides,
    )


@pytest.mark.parametrize(
    "headers,body,status,code",
    [
        ({"Host": "untrusted.example"}, {"enabled": True}, 400, "invalid_host"),
        ({"Origin": "https://untrusted.example"}, {"enabled": True}, 403, "invalid_origin"),
        ({"Origin": "null"}, {"enabled": True}, 403, "invalid_origin"),
        ({"Sec-Fetch-Site": "cross-site"}, {"enabled": True}, 403, "invalid_origin"),
        ({}, {"enabled": True, "large": "x" * 128}, 413, "request_too_large"),
    ],
)
def test_rejected_requests_do_not_create_runtime_state(
    tmp_path: Path, headers: dict[str, str], body: dict[str, object], status: int, code: str
) -> None:
    app = create_app(settings=settings(tmp_path, max_body_bytes=64))
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.put("/api/v1/capture", json=body, headers=headers)
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert not list(tmp_path.iterdir())


def test_liveness_is_independent_of_database_readiness(tmp_path: Path) -> None:
    with TestClient(create_app(), base_url="http://127.0.0.1:8001") as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 503


def test_text_limit_and_routing_failures_use_the_error_contract(tmp_path: Path) -> None:
    with TestClient(
        create_app(settings=settings(tmp_path)), base_url="http://127.0.0.1:8001"
    ) as client:
        response = client.put(
            "/api/v1/transcripts/0198f100-0000-7000-8000-000000000001/text",
            json={"text": "x" * 32_001, "expected_revision": 1},
        )
        assert response.status_code == 422
        assert response.json()["error"]["issues"]
        assert "x" * 100 not in response.text
        missing = client.get("/api/v1/unknown")
        assert missing.json()["error"]["status"] == 404
        method = client.patch("/api/v1/capture")
        assert method.json()["error"]["status"] == 405


def test_rate_limit_is_applied_before_runtime_creation(tmp_path: Path) -> None:
    with TestClient(
        create_app(settings=settings(tmp_path, requests_per_minute=1)),
        base_url="http://127.0.0.1:8001",
    ) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        response = client.get("/api/v1/health/live")
        assert response.status_code == 429
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_streamed_bodies_are_bounded_without_content_length(tmp_path: Path) -> None:
    called = False

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        nonlocal called
        called = True

    boundary = LocalHttpBoundary(app, settings=settings(tmp_path, max_body_bytes=4))
    chunks = iter([b"abc", b"def"])

    async def receive() -> Message:
        return {"type": "http.request", "body": next(chunks), "more_body": True}

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    await boundary({"type": "http", "headers": [(b"host", b"127.0.0.1")]}, receive, send)
    assert messages[0]["status"] == 413
    assert not called


@pytest.mark.asyncio
async def test_request_admission_is_bounded_and_recovers_after_timeout(tmp_path: Path) -> None:
    entered = asyncio.Event()

    async def app(_scope: Any, _receive: Any, _send: Any) -> None:
        entered.set()
        await asyncio.Event().wait()

    boundary = LocalHttpBoundary(
        app, settings=settings(tmp_path, max_concurrent_requests=1, request_timeout=0.02)
    )
    scope: Any = {"type": "http", "headers": [(b"host", b"127.0.0.1")]}

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    first_messages: list[Message] = []

    async def first_send(message: Message) -> None:
        first_messages.append(message)

    first = asyncio.create_task(boundary(dict(scope), receive, first_send))
    await entered.wait()
    second_messages: list[Message] = []

    async def second_send(message: Message) -> None:
        second_messages.append(message)

    await boundary(dict(scope), receive, second_send)
    assert second_messages[0]["status"] == 503
    await first
    assert first_messages[0]["status"] == 504
    third_messages: list[Message] = []

    async def third_send(message: Message) -> None:
        third_messages.append(message)

    await boundary(dict(scope), receive, third_send)
    assert third_messages[0]["status"] == 504


def test_unexpected_errors_are_private_and_logged_once(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app()

    async def broken() -> None:
        raise RuntimeError("private transcript text")

    app.add_api_route("/api/v1/broken", broken, methods=["POST"])
    with TestClient(app, base_url="http://127.0.0.1:8001", raise_server_exceptions=False) as client:
        response = client.post("/api/v1/broken")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        request_id = response.headers["x-request-id"]
    assert "private transcript text" not in response.text + caplog.text
    assert caplog.text.count('"event": "request_failed"') == 1
    assert request_id in caplog.text
