"""The ports the entitlements module runs on, set once at start-up (or by a test)."""

from dataclasses import dataclass

from platform_api.entitlements.keys import ContactKey
from platform_api.entitlements.store import EntitlementStore
from platform_api.shared.bus import EventBus


@dataclass
class Runtime:
    store: EntitlementStore
    key: ContactKey
    bus: EventBus


_runtime: Runtime | None = None


def set_runtime(runtime: Runtime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("entitlements runtime is not configured")
    return _runtime
