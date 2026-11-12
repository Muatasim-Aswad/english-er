#!/usr/bin/env python3
"""Validate a source-only release without changing Git or contacting GitHub."""

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_notes(tag: str) -> str:
    version = tomllib.loads((ROOT / "apps/backend/pyproject.toml").read_text())["project"][
        "version"
    ]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag) or tag != f"v{version}":
        raise SystemExit("Tag must match the authoritative product version")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    section = re.search(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}\n(.*?)(?=^## |\Z)",
        changelog,
        re.MULTILINE | re.DOTALL,
    )
    if section is None or not section[1].strip():
        raise SystemExit("A dated changelog section is required for this version")
    return section[1].strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--notes-file", type=Path)
    args = parser.parse_args()
    notes = release_notes(args.tag)
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if dirty:
        raise SystemExit("Release checks require clean tracked and untracked source")
    tag_revision = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{args.tag}^{{commit}}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if tag_revision.returncode == 0 and tag_revision.stdout.strip() != revision:
        raise SystemExit("Release tag must identify the checked-out commit")
    if args.notes_file:
        args.notes_file.write_text(notes)
    print(f"PASS {args.tag} at {revision}")


if __name__ == "__main__":
    main()
