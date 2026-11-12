import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from english_er.entrypoints.http import create_app
from english_er.infra.build import VERSION, source_build


def test_build_identity_rejects_dirty_and_missing_git(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "source.txt"
    source.write_text("synthetic source")
    subprocess.run(["git", "-C", str(tmp_path), "add", "source.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture Author",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    clean = source_build(tmp_path)
    assert clean["revision"] != "dev"
    assert clean["commit_time"] == clean["build_time"]
    source.write_text("modified source")
    assert source_build(tmp_path)["revision"] == "dev"
    source.write_text("synthetic source")
    (tmp_path / "untracked.txt").write_text("unreviewed source")
    assert source_build(tmp_path)["revision"] == "dev"
    missing = tmp_path / "export"
    missing.mkdir()
    assert source_build(missing)["revision"] == "dev"


def test_deterministic_build_epoch(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    assert source_build(tmp_path)["build_time"] == "1970-01-01T00:00:00+00:00"


def test_served_identity_is_uncached_and_does_not_acquire_runtime(tmp_path: Path) -> None:
    identity = {
        "version": VERSION,
        "revision": "a" * 40,
        "commit_time": "2026-11-12T00:00:00Z",
        "build_time": "2026-11-12T00:00:00Z",
    }
    (tmp_path / "version.json").write_text(json.dumps(identity))
    app = create_app(static_root=tmp_path)
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/version.json")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == identity
        (tmp_path / "version.json").write_text(json.dumps({**identity, "revision": "b" * 40}))
        assert client.get("/version.json").json() == identity
    assert app.openapi()["info"]["version"] == VERSION


def test_installed_version_works_outside_git(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-c",
        "from english_er.entrypoints.cli import main; main(['--version'])",
    ]
    result = subprocess.run(command, cwd=tmp_path, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == VERSION
