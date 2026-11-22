from typing import Any

import pytest


@pytest.fixture
def lib(ent: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.library import runtime as runtime_module
    from platform_api.library.ports import InMemoryDownloadLog, InMemoryFileStore, InMemoryItemStore
    from platform_api.library.runtime import Runtime

    runtime = Runtime(
        items=InMemoryItemStore(),
        staging=InMemoryFileStore(),
        files=InMemoryFileStore(),
        downloads=InMemoryDownloadLog(),
        bus=ent.bus,
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime
