"""Whole journeys through HTTP: an owner's grant, a sign-in, a revoke, and what /v1/me says."""

from fastapi.testclient import TestClient

from platform_api.app import Deps, create_app
from platform_api.settings import Settings
from tests.admin.test_admin import sub_of, token
from tests.fixtures.people import EMAIL
from tests.identity.test_sessions import sign_in


def owner_client() -> TestClient:
    client = TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=sub_of)))
    client.headers["Authorization"] = f"Bearer {token('acc-1')}"
    return client


def test_di_is_paid_through_an_owner_grant_and_free_after_its_revoke(world, ent):
    owner = owner_client()
    made = owner.post(
        "/v1/admin/entitlements",
        json={"email": EMAIL["di"], "grant": "tier:paid", "months": 6, "reason": "comp reader"},
    )
    assert made.status_code == 200
    body = sign_in(world, "di").json()
    assert body["access"]["tier"] == "paid"
    cookie = {"X-Member-Session": body["session"]["cookie"]}
    assert world.get("/v1/me", headers=cookie).json()["access"]["tier"] == "paid"

    eid = made.json()["entitlement_id"]
    revoked = owner.post(f"/v1/admin/entitlements/{eid}/revoke", json={"reason": "ended"})
    assert revoked.status_code == 200
    assert world.get("/v1/me", headers=cookie).json()["access"]["tier"] == "free"


def test_ed_signs_in_free_and_is_not_recognised(world):
    body = sign_in(world, "ed").json()
    assert (body["access"]["tier"], body["join"]["recognition"]) == ("free", "free")
