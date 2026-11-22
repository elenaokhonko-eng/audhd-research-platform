"""Rate limits: a port and an in-memory implementation with fixed windows."""

import math
from datetime import datetime, timedelta
from typing import Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window: timedelta, now: datetime) -> int | None:
        """Count one use of `key`. None when allowed, else the seconds to wait."""
        ...


class InMemoryRateLimiter:
    """Fixed windows aligned to the epoch: at most `limit` uses per window and key."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, float], tuple[float, int]] = {}  # -> (start, used)

    def hit(self, key: str, limit: int, window: timedelta, now: datetime) -> int | None:
        size = window.total_seconds()
        if size <= 0 or limit < 1:
            raise ValueError("a limit needs a positive window and at least one use")
        stamp = now.timestamp()
        start = math.floor(stamp / size) * size
        held_start, used = self._windows.get((key, size), (start, 0))
        if held_start != start:
            used = 0  # a new window: the old one is forgotten
        if used >= limit:
            return max(1, math.ceil(start + size - stamp))
        self._windows[(key, size)] = (start, used + 1)
        return None
