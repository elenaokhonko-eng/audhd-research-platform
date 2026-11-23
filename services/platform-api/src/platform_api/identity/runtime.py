"""The ports the identity module runs on, set once at start-up (or by a test)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from platform_api.identity.provider import IdentityProvider
from platform_api.identity.store import MemberStore
from platform_api.shared.bus import EventBus
from platform_api.shared.ratelimit import RateLimiter


@dataclass
class Runtime:
    members: MemberStore
    provider: IdentityProvider
    bus: EventBus
    session_ttl: timedelta
    limiter: RateLimiter
    # None until the Commerce lane wires its request_refresh; its "already_running" is
    # passed on as "started".
    request_refresh: Callable[[str, datetime], Literal["fresh", "started"]] | None
    last_reconcile_at: Callable[[], datetime | None] | None


_runtime: Runtime | None = None


def set_runtime(runtime: Runtime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("identity runtime is not configured")
    return _runtime
