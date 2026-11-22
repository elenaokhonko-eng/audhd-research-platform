"""The ports the library module runs on, set once at start-up (or by a test)."""

from dataclasses import dataclass

from platform_api.library.ports import DownloadLog, FileStore, ItemStore
from platform_api.shared.bus import EventBus


@dataclass
class Runtime:
    items: ItemStore
    staging: FileStore
    files: FileStore
    downloads: DownloadLog
    bus: EventBus


_runtime: Runtime | None = None


def set_runtime(runtime: Runtime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("library runtime is not configured")
    return _runtime
