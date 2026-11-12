"""Backend command-line entry point."""

import argparse
import json
from collections.abc import Sequence

from english_er.entrypoints.worker import main as worker_main
from english_er.infra.build import VERSION, source_build


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="English-er backend commands")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("command", choices=("worker", "build-info"))
    arguments, remaining = parser.parse_known_args(argv)
    if arguments.command == "worker":
        worker_main(remaining)
    elif arguments.command == "build-info":
        print(json.dumps(source_build(), sort_keys=True))
