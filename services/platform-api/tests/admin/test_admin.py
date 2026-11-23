import base64
import json
import logging

import pytest
from fastapi.testclient import TestClient

from platform_api.app import Deps, create_app
from platform_api.settings import Settings
from tests.entitlements.test_campaigns import campaign
from tests.fixtures.people import EMAIL


def token(sub):
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{part({'alg': 'none'})}.{part({'sub': sub, 'email_verified': True})}.x"


def sub_of(tok):  # stands in for Google's signature check
    from platform_api.shared.auth import NotAuthorised

    try:
        payload = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]
    except Exception as exc:
        raise NotAuthorised("invalid") from exc


@pytest.fixture
def admin(idn, ent):
    client = TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=sub_of)))
    client.headers["Authorization"] = f"Bearer {token('acc-1')}"
    return client


def test_only_a_listed_account_gets_in(admin):
    for headers in (
        {"Authorization": f"Bearer {token('acc-2')}"},
        {"Authorization": "Bearer junk"},
        {"Authorization": ""},
    ):
        r = admin.get("/v1/admin/launch/report", headers=headers)
        assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert admin.get("/v1/admin/launch/report").status_code == 200


def test_without_a_verifier_nobody_gets_in(idn, ent):
    client = TestClient(create_app(Settings(owner_accounts=["acc-1"])))
    assert (
        client.get(
            "/v1/admin/launch/report", headers={"Authorization": f"Bearer {token('acc-1')}"}
        ).status_code
        == 403
    )


def test_the_owner_list_reads_a_comma_separated_variable(monkeypatch):
    monkeypatch.setenv("PLATFORM_OWNER_ACCOUNTS", "acc-1, acc-2")
    assert Settings().owner_accounts == ["acc-1", "acc-2"]


def test_an_empty_owner_list_allows_nobody(idn, ent):
    client = TestClient(create_app(Settings(owner_accounts=[]), Deps(verify_owner=sub_of)))
    assert (
        client.get(
            "/v1/admin/launch/report", headers={"Authorization": f"Bearer {token('acc-1')}"}
        ).status_code
        == 403
    )


def test_grant_search_and_revoke_by_hand(admin, ent, caplog):
    with caplog.at_level(logging.DEBUG):
        made = admin.post(
            "/v1/admin/entitlements",
            json={"email": EMAIL["di"], "grant": "tier:paid", "months": 6, "reason": "comp reader"},
        )
        found = admin.post("/v1/admin/contacts/search", json={"email": " DI@example.org"}).json()[
            "contact"
        ]
    eid = made.json()["entitlement_id"]
    assert [e["entitlement_id"] for e in found["entitlements"]] == [eid] and found[
        "has_member"
    ] is False
    assert "@" not in json.dumps(found) and "@" not in caplog.text
    assert (
        admin.post(f"/v1/admin/entitlements/{eid}/revoke", json={"reason": "mistake"}).status_code
        == 200
    )
    assert admin.post("/v1/admin/entitlements/nope/revoke", json={"reason": "x"}).status_code == 404
    assert admin.post("/v1/admin/contacts/search", json={"email": EMAIL["bo"]}).json() == {
        "contact": None
    }


def test_a_grant_needs_exactly_one_end_and_a_reason(admin):
    base = {"email": EMAIL["di"], "grant": "tier:paid"}
    for extra in (
        {"reason": "r"},
        {"months": 6, "valid_until": "2027-01-01T00:00:00Z", "reason": "r"},
        {"months": 6, "reason": ""},
    ):
        assert admin.post("/v1/admin/entitlements", json={**base, **extra}).status_code == 422


def test_every_call_is_audited_reads_included(admin, ent):
    admin.get("/v1/admin/support-requests")
    admin.put("/v1/admin/launch", json={"join_open": True})
    actions = [(a.actor, a.action) for a in ent.store.audit_for("admin")]
    assert actions == [("owner:acc-1", "admin.read"), ("owner:acc-1", "launch.switched")]


def test_campaigns_are_validated_and_counts_survive_a_rewrite(admin, ent):
    one = campaign().model_dump(mode="json")
    default = campaign("members", audience="public", grant=None, is_default=True).model_dump(
        mode="json"
    )
    assert (
        admin.put("/v1/admin/campaigns", json={"campaigns": [one]}).status_code == 422
    )  # no default
    assert (
        admin.put("/v1/admin/campaigns", json={"campaigns": [one, one, default]}).status_code == 422
    )
    assert admin.put("/v1/admin/campaigns", json={"campaigns": [one, default]}).json() == {
        "written": 2
    }
    ent.store.add_to_campaign_count("founding", "arrivals")
    admin.put("/v1/admin/campaigns", json={"campaigns": [one, default]})
    assert ent.store.get_campaign("founding").counts["arrivals"] == 1


def test_launch_switches_take_a_subset_and_report_counts(admin):
    assert (
        admin.put(
            "/v1/admin/launch", json={"join_open": True, "required_terms_version": "2026-11-23"}
        ).json()["join_open"]
        is True
    )
    stored = admin.put("/v1/admin/launch", json={"library_open": True}).json()
    assert (stored["join_open"], stored["library_open"], stored["required_terms_version"]) == (
        True,
        True,
        "2026-11-23",
    )
    assert admin.put("/v1/admin/launch", json={"join_open": "maybe"}).status_code == 422


# Added by the controller's rulings for this task.


def test_no_admin_answer_or_log_line_carries_the_token(admin, ent, caplog):
    tok = token("acc-1")
    default = campaign("members", audience="public", grant=None, is_default=True).model_dump(
        mode="json"
    )
    calls = [
        ("post", "/v1/admin/contacts/search", {"email": EMAIL["ana"]}),
        (
            "post",
            "/v1/admin/entitlements",
            {"email": EMAIL["ana"], "grant": "tier:paid", "months": 1, "reason": "r"},
        ),
        ("post", "/v1/admin/entitlements/nope/revoke", {"reason": "r"}),
        ("put", "/v1/admin/campaigns", {"campaigns": [default]}),
        ("put", "/v1/admin/launch", {"join_open": True}),
        ("put", "/v1/admin/launch", {}),
        ("get", "/v1/admin/launch/report", None),
        ("get", "/v1/admin/support-requests", None),
    ]
    bodies = []
    with caplog.at_level(logging.DEBUG):
        for method, path, body in calls:
            kwargs = {"json": body} if body is not None else {}
            bodies.append(getattr(admin, method)(path, **kwargs).text)
            bodies.append(
                getattr(admin, method)(
                    path, headers={"Authorization": f"Bearer {token('acc-2')}"}, **kwargs
                ).text
            )
    assert all(tok not in b and "acc-2" not in b for b in bodies)
    assert tok not in caplog.text and token("acc-2") not in caplog.text


def test_a_refusal_is_the_same_whatever_the_cause(admin):
    def refuse(tok):
        raise RuntimeError("verifier down")

    seen = {
        admin.get("/v1/admin/launch/report", headers={"Authorization": h}).text
        for h in ("", "Basic x", "Bearer ", f"Bearer {token('acc-2')}")
    }
    broken = TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=refuse)))
    seen.add(
        broken.get(
            "/v1/admin/launch/report", headers={"Authorization": f"Bearer {token('acc-1')}"}
        ).text
    )
    seen.add(admin.get("/v1/admin/launch/report", headers={"Authorization": "Bearer junk"}).text)
    assert len(seen) == 1


def test_a_crash_holding_an_address_leaves_no_traceback_in_the_log(idn, ent, caplog):
    app = create_app(Settings())

    @app.get("/v1/_crash")
    def crash():
        raise RuntimeError(EMAIL["ana"])

    async def like_uvicorn(scope, receive, send):
        # Uvicorn logs whatever escapes the application, traceback and message included.
        try:
            await app(scope, receive, send)
        except Exception as exc:
            logging.getLogger("uvicorn.error").error("Exception in ASGI application", exc_info=exc)

    with caplog.at_level(logging.DEBUG):
        r = TestClient(like_uvicorn, raise_server_exceptions=False).get("/v1/_crash")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert "@" not in caplog.text and "@" not in r.text
    assert "RuntimeError" in caplog.text  # the fault is still visible, without its text


def test_a_google_token_is_accepted_only_from_google_with_a_verified_address(monkeypatch):
    from google.oauth2 import id_token

    from platform_api.shared.auth import NotAuthorised, google_account_from_token

    claims = {"iss": "https://accounts.google.com", "sub": "acc-1", "email_verified": True}
    monkeypatch.setattr(id_token, "verify_token", lambda tok, request: dict(claims))
    assert google_account_from_token("t") == "acc-1"
    for bad in ({"iss": "https://evil.example.org"}, {"email_verified": False}, {"sub": ""}):
        monkeypatch.setattr(
            id_token, "verify_token", lambda tok, request, bad=bad: {**claims, **bad}
        )
        with pytest.raises(NotAuthorised):
            google_account_from_token("t")

    def expired(tok, request):
        raise ValueError("Token expired")

    monkeypatch.setattr(id_token, "verify_token", expired)
    with pytest.raises(NotAuthorised):
        google_account_from_token("t")


# Fix round 1: every call by a verified owner leaves exactly one route-level entry.


def route_entries(ent, subject):
    return [
        (a.actor, a.action, a.evidence["outcome"])
        for a in ent.store.audit_for(subject)
        if "route" in a.evidence
    ]


def test_a_revoke_that_changes_nothing_is_still_audited_once_per_call(admin, ent):
    made = admin.post(
        "/v1/admin/entitlements",
        json={"email": EMAIL["di"], "grant": "tier:paid", "months": 6, "reason": "comp"},
    )
    eid = made.json()["entitlement_id"]
    for _ in range(2):
        assert (
            admin.post(
                f"/v1/admin/entitlements/{eid}/revoke", json={"reason": "mistake"}
            ).status_code
            == 200
        )
    assert route_entries(ent, eid) == [
        ("owner:acc-1", "entitlement.granted", "200"),
        ("owner:acc-1", "entitlement.revoked", "200"),
        ("owner:acc-1", "entitlement.revoked", "200"),
    ]


def test_a_refused_call_by_the_owner_is_audited_with_its_outcome(admin, ent):
    assert admin.post("/v1/admin/entitlements/nope/revoke", json={"reason": "x"}).status_code == 404
    assert route_entries(ent, "nope") == [("owner:acc-1", "entitlement.revoked", "404")]
    bad = {"email": EMAIL["di"], "grant": "tier:gold", "months": 6, "reason": "r"}
    assert admin.post("/v1/admin/entitlements", json=bad).status_code == 422
    from platform_api.entitlements.public import contact_id_for

    # A bad grant name is refused before a contact exists, so the entry names no contact.
    assert route_entries(ent, contact_id_for(EMAIL["di"])) == []
    no_end = {"email": EMAIL["di"], "grant": "tier:paid", "reason": "r"}
    assert admin.post("/v1/admin/entitlements", json=no_end).status_code == 422
    assert admin.put("/v1/admin/campaigns", json={"campaigns": []}).status_code == 422
    assert route_entries(ent, "admin") == [
        ("owner:acc-1", "entitlement.granted", "422"),
        ("owner:acc-1", "entitlement.granted", "422"),
        ("owner:acc-1", "campaign.written", "422"),
    ]


def test_a_refused_caller_leaves_no_entry(admin, ent):
    admin.get("/v1/admin/launch/report", headers={"Authorization": f"Bearer {token('acc-2')}"})
    assert ent.store.audit_for("admin") == []


def test_a_route_without_an_audit_action_cannot_be_added():
    from fastapi import APIRouter

    from platform_api.admin.http import AuditedRoute

    router = APIRouter(route_class=AuditedRoute)
    with pytest.raises(RuntimeError):

        @router.get("/v1/admin/undeclared")
        def undeclared():
            return {}


@pytest.mark.parametrize("name", ["status:substack_paid", "item:", "item:  ", "paid"])
def test_a_grant_with_a_bad_name_is_refused_before_any_contact_is_made(admin, ent, name):
    from platform_api.entitlements import public as ent_api

    r = admin.post(
        "/v1/admin/entitlements",
        json={"email": EMAIL["di"], "grant": name, "months": 6, "reason": "comp reader"},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])) is None
