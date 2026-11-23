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
    from platform_api.commerce.ports import InMemoryJobStarter, InMemoryRunStore
    from platform_api.commerce.runtime import Runtime
    from platform_api.commerce.settings import CommerceSettings
    from platform_api.shared.ratelimit import InMemoryRateLimiter

    settings = CommerceSettings(
        stripe_substack_application="ca_test_substack",
        substack_grant_year="tier:paid",
        reconcile_job="projects/p/locations/l/jobs/stripe-reconcile",
    )
    runtime = Runtime(
        settings=settings,
        stripe=None,
        runs=InMemoryRunStore(),
        bus=ent.bus,
        jobs=InMemoryJobStarter(),
        limiter=InMemoryRateLimiter(),
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


@pytest.fixture
def member_client(com, idn, ent):
    """Sign-in made possible, then `member_client(name)` -> (client, session header)."""
    from fastapi.testclient import TestClient

    from platform_api.app import create_app
    from platform_api.settings import Settings
    from tests.entitlements.test_campaigns import campaign
    from tests.identity.test_http_member import member

    config = ent.store.get_launch_config()
    ent.store.put_launch_config(
        config.model_copy(
            update={
                "join_open": True,
                "required_terms_version": "t1",
                "required_privacy_version": "p1",
            }
        )
    )
    if not any(c.is_default for c in ent.store.list_campaigns()):
        ent.store.put_campaigns(
            [campaign("members", audience="public", grant=None, is_default=True)]
        )
    client = TestClient(create_app(Settings()))

    def signed_in(name):
        return client, member(client, name)

    return signed_in
