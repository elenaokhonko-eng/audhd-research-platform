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


@pytest.fixture
def member_client(idn: Any, ent: Any) -> Any:
    """Sign a fixture person in, with their records waiting under their contact id, and accept
    the terms. Returns the client and the session header."""
    from fastapi.testclient import TestClient

    from platform_api.app import create_app
    from platform_api.entitlements import public as ent_api
    from platform_api.entitlements.models import ChannelsPatch, LaunchConfig, entitlement_id
    from platform_api.settings import Settings
    from tests.entitlements.test_campaigns import campaign
    from tests.fixtures.people import EMAIL, holdings
    from tests.identity.test_sessions import sign_in

    ent.store.put_launch_config(
        LaunchConfig(
            join_open=True,
            library_open=True,
            required_terms_version="t1",
            required_privacy_version="p1",
        )
    )
    ent.store.put_campaigns([campaign("members", audience="public", grant=None, is_default=True)])
    client = TestClient(create_app(Settings()))

    def make(name: str) -> tuple[TestClient, dict[str, str]]:
        contact_id = ent_api.upsert_contact(EMAIL[name], ChannelsPatch())
        # Sign-in claims only what waits under the contact id of the address.
        held = [
            e.model_copy(
                update={
                    "contact_id": contact_id,
                    "entitlement_id": entitlement_id(e.source, e.source_ref, contact_id, e.grant),
                }
            )
            for e in holdings(name)
        ]
        ent.store.write(contact_id, held, [])
        cookie = {"X-Member-Session": sign_in(client, name).json()["session"]["cookie"]}
        accepted = client.post(
            "/v1/me/terms-acceptance",
            headers=cookie,
            json={"terms_version": "t1", "privacy_version": "p1"},
        )
        assert accepted.status_code == 200
        return client, cookie

    return make


@pytest.fixture
def owner_client(idn: Any, ent: Any) -> Any:
    """A client that calls as the owner account `acc-1`."""
    from fastapi.testclient import TestClient

    from platform_api.app import Deps, create_app
    from platform_api.settings import Settings
    from tests.admin.test_admin import sub_of, token

    client = TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=sub_of)))
    client.headers["Authorization"] = f"Bearer {token('acc-1')}"
    return client
