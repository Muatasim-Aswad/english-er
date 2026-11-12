"""An advisory lock prevents overlapping recovery or correction workers."""

import fcntl
import os
from pathlib import Path
from types import TracebackType


class WorkerOwnership:
    def __init__(self, state_root: Path) -> None:
        self.path = state_root / "worker.lock"
        self.descriptor: int | None = None

    def __enter__(self) -> "WorkerOwnership":
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(descriptor)
            raise RuntimeError("Another English-er worker owns this state directory") from None
        self.descriptor = descriptor
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _error: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None
