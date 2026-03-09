"""Discord-compatible snowflake ID generator.

Format (64 bits):
  - 42 bits: milliseconds since Discord epoch (2015-01-01T00:00:00Z)
  -  5 bits: worker ID
  -  5 bits: process ID
  - 12 bits: per-process increment
"""

from __future__ import annotations

import threading
import time

from digitaltwin.config import DISCORD_EPOCH

_lock = threading.Lock()
_increment = 0
_WORKER_ID = 1
_PROCESS_ID = 0


def generate_snowflake() -> str:
    global _increment
    with _lock:
        ts = int(time.time() * 1000) - DISCORD_EPOCH
        sf = (
            (ts << 22)
            | (_WORKER_ID << 17)
            | (_PROCESS_ID << 12)
            | (_increment & 0xFFF)
        )
        _increment += 1
    return str(sf)


def snowflake_timestamp(snowflake: str | int) -> float:
    """Return the Unix timestamp (seconds) embedded in a snowflake."""
    return ((int(snowflake) >> 22) + DISCORD_EPOCH) / 1000
