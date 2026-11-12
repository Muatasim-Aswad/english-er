from contextlib import suppress
from pathlib import Path


def remove_audio_files(audio_root: Path, relative_paths: list[str]) -> None:
    for relative_path in relative_paths:
        candidate = (audio_root / relative_path).resolve()
        with suppress(OSError, ValueError):
            candidate.relative_to(audio_root.resolve())
            candidate.unlink(missing_ok=True)
