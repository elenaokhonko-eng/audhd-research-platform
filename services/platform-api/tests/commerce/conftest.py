import os

import pytest


@pytest.fixture(autouse=True)
def _ignore_platform_environment(monkeypatch):
    for name in [n for n in os.environ if n.startswith("PLATFORM_")]:
        monkeypatch.delenv(name)
