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


@pytest.fixture
def com(ent, monkeypatch):
    from platform_api.commerce import runtime as runtime_module
    from platform_api.commerce.ports import InMemoryRunStore
    from platform_api.commerce.runtime import Runtime
    from platform_api.commerce.settings import CommerceSettings

    settings = CommerceSettings(
        stripe_substack_application="ca_test_substack",
        substack_grant_year="tier:paid",
        reconcile_job="projects/p/locations/l/jobs/stripe-reconcile",
    )
    runtime = Runtime(settings=settings, stripe=None, runs=InMemoryRunStore(), bus=ent.bus)
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime
