"""The ports the commerce module runs on, set once at start-up (or by a test)."""

from dataclasses import dataclass

from platform_api.commerce.ports import RosterInbox, RunStore, StripeReader
from platform_api.commerce.settings import CommerceSettings
from platform_api.shared.bus import EventBus


@dataclass
class Runtime:
    settings: CommerceSettings
    stripe: StripeReader | None
    runs: RunStore
    bus: EventBus
    inbox: RosterInbox | None = None


_runtime: Runtime | None = None


def set_runtime(runtime: Runtime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("commerce runtime is not configured")
    return _runtime
