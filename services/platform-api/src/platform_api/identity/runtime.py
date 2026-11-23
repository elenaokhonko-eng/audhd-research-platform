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
    # Set by `adapters.configure_runtimes`: `adapters.sign_in_refresh`, which passes
    # Commerce's "already_running" on as "started", and `adapters.sign_in_last_reconcile`
    # (Commerce's `last_reconcile_completed_at`). Neither raises. None only in a test that
    # leaves Commerce out.
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
