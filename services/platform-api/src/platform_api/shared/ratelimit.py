"""Rate limits: a port and an in-memory implementation with fixed windows."""

import math
from datetime import datetime, timedelta
from typing import Protocol


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window: timedelta, now: datetime) -> int | None:
        """Count one use of `key`. None when allowed, else the seconds to wait."""
        ...


def count_hit(
    held: tuple[float, int] | None, limit: int, window: timedelta, now: datetime
) -> tuple[tuple[float, int], int | None]:
    """One use counted against a fixed window aligned to the epoch.

    `held` is the stored (window start, uses), or None. Returns the state to store and
    None when allowed, or the state unchanged and the seconds to wait when refused.
    """
    size = window.total_seconds()
    if size <= 0 or limit < 1:
        raise ValueError("a limit needs a positive window and at least one use")
    stamp = now.timestamp()
    start = math.floor(stamp / size) * size
    held_start, used = held if held is not None else (start, 0)
    if held_start != start:
        used = 0  # a new window: the old one is forgotten
    if used >= limit:
        return (start, used), max(1, math.ceil(start + size - stamp))
    return (start, used + 1), None


class InMemoryRateLimiter:
    """Fixed windows aligned to the epoch: at most `limit` uses per window and key."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, float], tuple[float, int]] = {}  # -> (start, used)

    def hit(self, key: str, limit: int, window: timedelta, now: datetime) -> int | None:
        slot = (key, window.total_seconds())
        state, wait = count_hit(self._windows.get(slot), limit, window, now)
        if wait is None:
            self._windows[slot] = state
        return wait
