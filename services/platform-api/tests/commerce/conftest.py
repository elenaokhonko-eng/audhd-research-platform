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
    from platform_api.commerce.ports import (
        InMemoryJobStarter,
        InMemoryPromotionStore,
        InMemoryRunStore,
    )
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
        promotions=InMemoryPromotionStore(),
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


@pytest.fixture
def member_client(com, idn, ent, monkeypatch):
    """Sign-in made possible, then `member_client(name)` -> (client, session header).

    The clock is fixed in the middle of a minute, so that two requests of one test never
    fall on either side of a minute's edge.
    """
    from datetime import timedelta

    from fastapi.testclient import TestClient

    from platform_api.app import create_app
    from platform_api.settings import Settings
    from platform_api.shared import clock
    from tests.entitlements.test_campaigns import campaign
    from tests.fixtures.people import T0
    from tests.identity.test_http_member import member

    monkeypatch.setattr(clock, "utcnow", lambda: T0 + timedelta(seconds=30))

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


@pytest.fixture
def signed_in(com, member_client):
    """`signed_in(name)` -> the member's uid, signed in as `member_client` signs a person in.

    The first call runs one real reconcile at `T0` with ana's annual and hal's monthly
    subscription, so that ana is paid, hal pays Substack on a plan without the platform,
    and anyone else is free.
    """
    from platform_api.commerce import public as commerce
    from platform_api.commerce.ports import InMemoryStripeReader
    from tests.commerce.test_mapping import sub
    from tests.fixtures.people import T0

    reconciled = []

    def sign_in(name):
        if not reconciled:
            held, com.stripe = (
                com.stripe,
                InMemoryStripeReader([sub("ana"), sub("hal", interval="month")]),
            )
            commerce.stripe_reconcile(False, "schedule", T0)
            com.stripe = held
            reconciled.append(True)
        client, header = member_client(name)
        return client.get("/v1/me", headers=header).json()["member"]["uid"]

    return sign_in


@pytest.fixture
def owner_client(com, idn, ent):
    """A test client whose `Authorization` header passes the `owner` dependency as acc-1."""
    from fastapi.testclient import TestClient

    from platform_api.app import Deps, create_app
    from platform_api.settings import Settings
    from tests.admin.test_admin import sub_of, token

    client = TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=sub_of)))
    client.headers["Authorization"] = f"Bearer {token('acc-1')}"
    return client
