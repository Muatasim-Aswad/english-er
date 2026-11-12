import os
import stat
from dataclasses import dataclass
from pathlib import Path

from english_er.shared.errors import AppError


@dataclass(frozen=True, slots=True)
class CaptureControl:
    marker: Path

    def get(self) -> bool:
        try:
            return self.marker.exists()
        except OSError as error:
            raise AppError("capture_unavailable", "Capture state is unavailable.") from error

    def set(self, enabled: bool) -> bool:
        try:
            if enabled:
                self.marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                try:
                    descriptor = os.open(self.marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    if not stat.S_ISREG(self.marker.lstat().st_mode):
                        raise AppError(
                            "capture_unavailable",
                            "Capture state could not be changed.",
                        ) from None
                else:
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            else:
                self.marker.unlink(missing_ok=True)
            return self.get()
        except OSError as error:
            raise AppError("capture_unavailable", "Capture state could not be changed.") from error
