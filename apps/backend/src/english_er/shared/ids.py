"""UUIDv7 generation compatible with the project's Python 3.12 runtime."""

import secrets
import time
from uuid import UUID


def uuid7() -> UUID:
    timestamp_ms = time.time_ns() // 1_000_000
    value = (timestamp_ms & ((1 << 48) - 1)) << 80
    value |= 7 << 76
    value |= secrets.randbits(12) << 64
    value |= 2 << 62
    value |= secrets.randbits(62)
    return UUID(int=value)
