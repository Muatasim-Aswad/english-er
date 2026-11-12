from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from english_er.entrypoints.http import create_app
from english_er.modules.capture.dto import CaptureState


def operations(schema: dict[str, object]) -> Iterator[tuple[str, str]]:
    paths = schema["paths"]
    assert isinstance(paths, dict)
    for path, item in paths.items():
        assert isinstance(path, str)
        assert isinstance(item, dict)
        for method in item:
            if method in {"get", "put", "post", "delete"}:
                yield method.upper(), path


def test_factory_exposes_the_complete_v1_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    schema = create_app().openapi()

    assert set(operations(schema)) == {
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/health/live"),
        ("GET", "/api/v1/health/ready"),
        ("GET", "/api/v1/capture"),
        ("PUT", "/api/v1/capture"),
        ("GET", "/api/v1/transcripts"),
        ("GET", "/api/v1/transcripts/{id}"),
        ("POST", "/api/v1/transcripts/{id}/audio"),
        ("PUT", "/api/v1/transcripts/{id}/text"),
        ("PUT", "/api/v1/transcripts/{id}/review"),
        ("POST", "/api/v1/transcripts/{id}/retry"),
        ("DELETE", "/api/v1/transcripts/{id}"),
    }
    assert set(tmp_path.iterdir()) == before


def test_stub_health_and_empty_list_need_no_database() -> None:
    client = TestClient(create_app(), base_url="http://127.0.0.1:8001")

    assert client.get("/api/v1/health").json() == {"api": "ok", "database": "unavailable"}
    assert client.get("/api/v1/capture").json() == {"enabled": False}
    assert client.get("/api/v1/transcripts").json() == {
        "items": [],
        "metadata": {"next_cursor": None},
    }
    response = client.put("/api/v1/capture", json={"enabled": True})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_contract_models_are_strict() -> None:
    with pytest.raises(ValidationError):
        CaptureState.model_validate({"enabled": 1})
    with pytest.raises(ValidationError):
        CaptureState.model_validate({"enabled": True, "unexpected": "value"})


def test_every_operation_declares_success_and_error_responses() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    assert isinstance(paths, dict)

    for _method, path in operations(schema):
        item = paths[path]
        assert isinstance(item, dict)
        operation = next(
            value
            for key, value in item.items()
            if key.upper() == _method and isinstance(value, dict)
        )
        responses = operation["responses"]
        assert isinstance(responses, dict)
        assert any(code.startswith("2") for code in responses)
        assert any(code.startswith(("4", "5")) for code in responses)
