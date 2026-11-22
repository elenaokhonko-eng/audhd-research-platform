import logging
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    """Put the root logger and uvicorn loggers back after a test reconfigures them."""
    names = ["", "uvicorn", "uvicorn.error", "uvicorn.access"]
    saved = [(lg, lg.handlers[:], lg.level, lg.propagate) for lg in map(logging.getLogger, names)]
    yield
    for lg, handlers, level, propagate in saved:
        lg.handlers[:] = handlers
        lg.setLevel(level)
        lg.propagate = propagate


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test depends on the real date."""
    from tests.fixtures.people import T0

    try:
        from platform_api.shared import clock
    except ImportError:
        return
    monkeypatch.setattr(clock, "utcnow", lambda: T0)


@pytest.fixture(autouse=True)
def _runtimes_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test that sets a runtime (main, a job) leaves the next test as it found it."""
    import importlib

    for name in ("entitlements", "identity"):
        try:
            module = importlib.import_module(f"platform_api.{name}.runtime")
        except ImportError:
            continue
        monkeypatch.setattr(module, "_runtime", module._runtime)


@pytest.fixture
def ent(monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.entitlements import runtime as runtime_module
    from platform_api.entitlements.keys import LocalContactKey
    from platform_api.entitlements.runtime import Runtime
    from platform_api.entitlements.store import InMemoryStore
    from platform_api.shared.bus import InMemoryBus

    runtime = Runtime(InMemoryStore(), LocalContactKey(b"test"), InMemoryBus())
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


@pytest.fixture
def idn(ent: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.identity import runtime as runtime_module
    from platform_api.identity.provider import FakeIdentityProvider
    from platform_api.identity.runtime import Runtime
    from platform_api.identity.store import InMemoryMemberStore
    from platform_api.shared.ratelimit import InMemoryRateLimiter
    from tests.fixtures.people import EMAIL

    runtime = Runtime(
        members=InMemoryMemberStore(),
        provider=FakeIdentityProvider(EMAIL),
        bus=ent.bus,
        session_ttl=timedelta(days=14),
        limiter=InMemoryRateLimiter(),
        request_refresh=None,
        last_reconcile_at=None,
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime
