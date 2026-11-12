#!/usr/bin/env python3
"""Render or remove English-er systemd user units."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

UNIT_NAMES = ("english-er-api.service", "english-er-worker.service")


def _quoted_unit_path(path: Path) -> str:
    value = str(path.resolve()).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def _unit_directory(path: Path) -> str:
    value = str(path.resolve()).replace("%", "%%")
    return "".join(
        character if character.isalnum() or character in "/_.-" else f"\\x{ord(character):02x}"
        for character in value
    )


def _default_unit_dir() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "systemd" / "user"


def _prepare_default_application_directories() -> None:
    for path in (
        Path.home() / ".local" / "share" / "english-er",
        Path.home() / ".local" / "state" / "english-er",
        Path.home() / ".cache" / "english-er",
    ):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)


def _unit_environment(name: str, value: Path) -> str:
    # Keep stable launcher symlinks (for example Mise's `latest` path) intact so
    # upgrading Codex does not leave the service pointing at a removed version.
    escaped = (
        f"{name}={value.absolute()}".replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    )
    return f'"{escaped}"'


def _render_units(repository_root: Path, codex_bin: Path) -> dict[str, str]:
    template_root = repository_root / "deploy" / "systemd"
    replacements = {
        "{{REPOSITORY_DIRECTORY}}": _unit_directory(repository_root),
        "{{REPOSITORY_ROOT}}": _quoted_unit_path(repository_root),
        "{{UVICORN_BIN}}": _quoted_unit_path(
            repository_root / "apps" / "backend" / ".venv" / "bin" / "uvicorn"
        ),
        "{{WORKER_BIN}}": _quoted_unit_path(
            repository_root / "apps" / "backend" / ".venv" / "bin" / "english-er-worker"
        ),
        "{{CODEX_ENVIRONMENT}}": _unit_environment("ENGLISH_ER_CODEX_EXECUTABLE", codex_bin),
    }
    rendered: dict[str, str] = {}
    for name in UNIT_NAMES:
        content = (template_root / f"{name}.in").read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        if "{{" in content or "}}" in content:
            raise RuntimeError(f"unresolved placeholder in {name}")
        rendered[name] = content
    return rendered


def _write_atomic(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print changes without writing")
    parser.add_argument("--uninstall", action="store_true", help="remove installed units")
    parser.add_argument("--unit-dir", type=Path, default=_default_unit_dir())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    unit_dir = arguments.unit_dir.expanduser().resolve()

    if arguments.uninstall:
        for name in UNIT_NAMES:
            target = unit_dir / name
            if arguments.dry_run:
                print(f"REMOVE {target}")
            else:
                target.unlink(missing_ok=True)
        if not arguments.dry_run:
            print(f"Removed English-er user units from {unit_dir}")
        return 0

    codex = shutil.which("codex")
    if codex is None:
        raise SystemExit("codex is required to render the worker service")
    rendered = _render_units(repository_root, Path(codex))
    if arguments.dry_run:
        for name, content in rendered.items():
            print(f"--- {unit_dir / name}")
            print(content, end="" if content.endswith("\n") else "\n")
        return 0

    _prepare_default_application_directories()
    unit_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    unit_dir.chmod(0o700)
    for name, content in rendered.items():
        _write_atomic(unit_dir / name, content)
    print(f"Installed English-er user units in {unit_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
