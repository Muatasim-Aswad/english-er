from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
INSTALLER = REPOSITORY_ROOT / "scripts" / "local_install.py"
DEPLOY = REPOSITORY_ROOT / "scripts" / "local_deploy.py"
UNIT_TEMPLATES = REPOSITORY_ROOT / "deploy" / "systemd"
CODEX_PROVIDER = REPOSITORY_ROOT / "apps" / "backend" / "src" / "english_er" / "infra" / "codex.py"

COMMON_HARDENING_DIRECTIVES = {
    "AmbientCapabilities=",
    "CapabilityBoundingSet=",
    "LockPersonality=true",
    "NoNewPrivileges=true",
    "PrivateTmp=true",
    "ProtectClock=true",
    "ProtectControlGroups=true",
    "ProtectHome=read-only",
    "ProtectHostname=true",
    "ProtectKernelLogs=true",
    "ProtectKernelModules=true",
    "ProtectKernelTunables=true",
    "ProtectSystem=strict",
    "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
    "RestrictNamespaces=true",
    "RestrictRealtime=true",
    "RestrictSUIDSGID=true",
    "UMask=0077",
}


def _run(
    script: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def _fake(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _installer_environment(root: Path) -> dict[str, str]:
    bin_dir = root / "fake-bin"
    bin_dir.mkdir()
    _fake(bin_dir / "codex", "exit 99")
    environment = os.environ.copy()
    environment["HOME"] = str(root / "home")
    environment["PATH"] = f"{bin_dir}:{os.defpath}"
    return environment


def test_installer_dry_run_renders_without_writing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    unit_dir = tmp_path / "units"
    environment = _installer_environment(tmp_path)

    completed = _run(
        INSTALLER,
        "--dry-run",
        "--unit-dir",
        str(unit_dir),
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert not home.exists()
    assert not unit_dir.exists()
    assert str(REPOSITORY_ROOT.resolve()) in completed.stdout
    assert "127.0.0.1" in completed.stdout
    assert f"ENGLISH_ER_CODEX_EXECUTABLE={tmp_path / 'fake-bin/codex'}" in completed.stdout
    assert "alembic" not in completed.stdout
    assert "capture-enabled" not in completed.stdout


def test_installer_preserves_stable_codex_symlink(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    versioned_dir = tmp_path / "installs" / "codex" / "0.1.0" / "bin"
    bin_dir.mkdir()
    versioned_dir.mkdir(parents=True)
    versioned_codex = versioned_dir / "codex"
    _fake(versioned_codex, "exit 0")
    stable_codex = bin_dir / "codex"
    stable_codex.symlink_to(versioned_codex)
    environment = os.environ.copy()
    environment["HOME"] = str(tmp_path / "home")
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"

    completed = _run(
        INSTALLER,
        "--dry-run",
        "--unit-dir",
        str(tmp_path / "units"),
        environment=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert f'Environment="ENGLISH_ER_CODEX_EXECUTABLE={stable_codex}"' in completed.stdout
    assert str(versioned_codex) not in completed.stdout


def test_installer_is_reversible_and_units_validate(tmp_path: Path) -> None:
    home = tmp_path / "home"
    unit_dir = tmp_path / "units"
    environment = _installer_environment(tmp_path)

    installed = _run(INSTALLER, "--unit-dir", str(unit_dir), environment=environment)
    assert installed.returncode == 0, installed.stderr
    units = [unit_dir / "english-er-api.service", unit_dir / "english-er-worker.service"]
    application_directories = [
        home / ".local" / "share" / "english-er",
        home / ".local" / "state" / "english-er",
        home / ".cache" / "english-er",
    ]
    assert all(unit.is_file() for unit in units)
    assert all(unit.stat().st_mode & 0o777 == 0o644 for unit in units)
    assert all(path.is_dir() for path in application_directories)
    assert all(path.stat().st_mode & 0o777 == 0o700 for path in application_directories)
    for unit in units:
        content = unit.read_text(encoding="utf-8")
        assert str(REPOSITORY_ROOT.resolve()) in content
        assert "{{" not in content
        assert "alembic" not in content

    verified = subprocess.run(
        ["systemd-analyze", "verify", *(str(unit) for unit in units)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr

    removed = _run(
        INSTALLER,
        "--uninstall",
        "--unit-dir",
        str(unit_dir),
        environment=environment,
    )
    assert removed.returncode == 0, removed.stderr
    assert not any(unit.exists() for unit in units)
    assert all(path.is_dir() for path in application_directories)


def test_installer_uninstall_does_not_prepare_application_directories(tmp_path: Path) -> None:
    home = tmp_path / "home"
    environment = os.environ.copy()
    environment["HOME"] = str(home)

    removed = _run(
        INSTALLER,
        "--uninstall",
        "--unit-dir",
        str(tmp_path / "units"),
        environment=environment,
    )

    assert removed.returncode == 0, removed.stderr
    assert not home.exists()


def test_deploy_aborts_before_restart_when_migration_fails(tmp_path: Path) -> None:
    log = tmp_path / "commands.log"
    fake_uv = tmp_path / "uv"
    fake_systemctl = tmp_path / "systemctl"
    _fake(fake_uv, "printf 'migration\\n' >>\"$ENGLISH_ER_TEST_LOG\"\nexit 17")
    _fake(fake_systemctl, 'printf \'restart %s\\n\' "$*" >>"$ENGLISH_ER_TEST_LOG"')
    environment = os.environ.copy()
    environment.update(
        {
            "ENGLISH_ER_TEST_LOG": str(log),
            "ENGLISH_ER_UV": str(fake_uv),
            "ENGLISH_ER_SYSTEMCTL": str(fake_systemctl),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
        }
    )

    completed = _run(DEPLOY, environment=environment)

    assert completed.returncode == 17
    assert log.read_text(encoding="utf-8").splitlines() == ["migration"]
    assert not (tmp_path / "state").exists()


def test_deploy_migrates_then_restarts_api_before_worker(tmp_path: Path) -> None:
    log = tmp_path / "commands.log"
    fake_uv = tmp_path / "uv"
    fake_systemctl = tmp_path / "systemctl"
    _fake(fake_uv, 'printf \'migration %s\\n\' "$*" >>"$ENGLISH_ER_TEST_LOG"')
    _fake(fake_systemctl, 'printf \'systemctl %s\\n\' "$*" >>"$ENGLISH_ER_TEST_LOG"')
    environment = os.environ.copy()
    environment.update(
        {
            "ENGLISH_ER_TEST_LOG": str(log),
            "ENGLISH_ER_UV": str(fake_uv),
            "ENGLISH_ER_SYSTEMCTL": str(fake_systemctl),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
        }
    )

    completed = _run(DEPLOY, environment=environment)

    assert completed.returncode == 0, completed.stderr
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("migration run --offline --frozen --directory ")
    assert lines[0].endswith("/apps/backend alembic upgrade head")
    assert lines[1:] == [
        "systemctl --user restart english-er-api.service",
        "systemctl --user restart english-er-worker.service",
    ]
    assert not (tmp_path / "state").exists()


def test_templates_do_not_run_migrations_or_enable_capture() -> None:
    content = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(UNIT_TEMPLATES.glob("*.in"))
    )
    assert "alembic" not in content
    assert "capture-enabled" not in content


def test_unit_security_boundaries_and_provider_isolation() -> None:
    api = (UNIT_TEMPLATES / "english-er-api.service.in").read_text(encoding="utf-8")
    worker = (UNIT_TEMPLATES / "english-er-worker.service.in").read_text(encoding="utf-8")

    for unit in (api, worker):
        assert set(unit.splitlines()) >= COMMON_HARDENING_DIRECTIVES

    application_paths = "%h/.local/share/english-er %h/.local/state/english-er"
    assert f"ReadWritePaths={application_paths} %h/.cache/english-er" in api.splitlines()
    assert "CacheDirectory=english-er" in api.splitlines()
    assert "CacheDirectoryMode=0700" in api.splitlines()
    assert f"ReadWritePaths={application_paths} %h/.codex" in worker.splitlines()
    assert "PrivateDevices=false" in api.splitlines()
    assert "PrivateDevices=true" in worker.splitlines()
    assert "Environment=HF_HUB_OFFLINE=1" in api.splitlines()
    assert "%h/.codex" not in api
    assert "IPAddressDeny=any" in api.splitlines()
    assert "IPAddressAllow=localhost" in api.splitlines()

    provider = CODEX_PROVIDER.read_text(encoding="utf-8")
    for flag in ("--ephemeral", "--ignore-user-config", "--ignore-rules"):
        assert provider.count(f'"{flag}"') == 1


def test_migration_runs_from_a_cold_subprocess(tmp_path: Path) -> None:
    database = tmp_path / "cold.sqlite3"
    environment = os.environ.copy()
    environment["ENGLISH_ER_DATABASE_URL"] = f"sqlite+aiosqlite:///{database}"

    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPOSITORY_ROOT / "apps" / "backend",
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert database.is_file()
