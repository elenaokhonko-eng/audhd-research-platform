import os

import pytest


def _platform_names() -> list[str]:
    return [n for n in os.environ if n.startswith("PLATFORM_")]


# This file loads before the test modules, so settings built at import time see no PLATFORM_* variable.
for _name in _platform_names():
    del os.environ[_name]


@pytest.fixture(autouse=True)
def _ignore_platform_environment(monkeypatch):
    for name in _platform_names():
        monkeypatch.delenv(name)
