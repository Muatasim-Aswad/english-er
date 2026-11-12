"""Compose and exclusively own the persistent correction worker."""

import argparse
import asyncio
import json
import logging
import signal
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from english_er.config import Settings
from english_er.infra.build import source_build
from english_er.infra.database import Database, sqlite_url
from english_er.infra.ownership import WorkerOwnership
from english_er.modules.capture import IngestionWorker, Spool
from english_er.modules.corrections import CodexCorrectionProvider, CorrectionProcessor
from english_er.modules.corrections.worker import DEFAULT_POLL_INTERVAL_SECONDS, PersistentWorker


async def _run(args: argparse.Namespace, settings: Settings) -> None:
    provider_settings = Settings.model_validate(
        {**settings.model_dump(), "provider_timeout": args.provider_timeout}
    )
    with WorkerOwnership(args.state_root):
        database = Database.create(args.database_url)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for name in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(name, stop.set)
        worker = PersistentWorker(
            IngestionWorker(Spool(args.state_root), database.sessions),
            CorrectionProcessor(
                database.sessions,
                CodexCorrectionProvider(
                    executable=settings.codex_executable,
                    timeout_seconds=provider_settings.provider_timeout,
                ),
                retry_delay_seconds=args.retry_delay,
            ),
            poll_interval_seconds=args.poll_interval,
        )
        task = asyncio.create_task(worker.run_forever(stop=stop))
        stopping = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait({task, stopping}, return_when=asyncio.FIRST_COMPLETED)
            if task.done():
                await task
        finally:
            task.cancel()
            stopping.cancel()
            with suppress(asyncio.CancelledError):
                await task
            with suppress(asyncio.CancelledError):
                await stopping
            await database.close()
            for name in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(name)


def _parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the English-er persistent worker")
    parser.add_argument(
        "--database-url", default=settings.database_url or sqlite_url(settings.database_path)
    )
    parser.add_argument("--state-root", type=Path, default=settings.state_root)
    parser.add_argument("--provider-timeout", type=float, default=settings.provider_timeout)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    settings = Settings()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("english_er.worker").info(
        json.dumps({"event": "build_started", **source_build()})
    )
    try:
        asyncio.run(_run(_parser(settings).parse_args(argv), settings))
    except Exception:
        logging.getLogger("english_er.worker").error(
            json.dumps({"event": "worker_failed", "code": "internal_error"})
        )
        raise SystemExit("English-er worker failed; check its structured service log.") from None
