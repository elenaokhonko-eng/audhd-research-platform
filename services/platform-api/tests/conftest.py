import logging
from collections.abc import Iterator
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


@pytest.fixture
def ent() -> Iterator[Any]:
    from platform_api.entitlements.keys import LocalContactKey
    from platform_api.entitlements.runtime import Runtime, get_runtime, set_runtime
    from platform_api.entitlements.store import InMemoryStore
    from platform_api.shared.bus import InMemoryBus

    try:
        previous: Runtime | None = get_runtime()
    except RuntimeError:
        previous = None
    runtime = Runtime(InMemoryStore(), LocalContactKey(b"test"), InMemoryBus())
    set_runtime(runtime)
    yield runtime
    if previous is not None:
        set_runtime(previous)
