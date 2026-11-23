import logging
from datetime import timedelta

from tests.fixtures.launch import TERMS
from tests.fixtures.people import T0

# tests/fixtures/launch.py holds:
#     TERMS = LaunchConfig(join_open=True, required_terms_version="t1", required_privacy_version="p1")
#
# tests/identity/conftest.py holds the fixture (a fixture imported into a test module makes ruff report F811):
#     @pytest.fixture
#     def world(idn, ent):
#         ent.store.put_launch_config(TERMS)
#         ent.store.put_campaigns([campaign(), campaign("members", audience="public", grant=None, is_default=True)])
#         run(ent, [state("ana", "sub_a"), state("hal", "sub_h", grant="status:substack_paid", interval="month")])
#         return TestClient(create_app(Settings()))
#     with campaign, run and state imported from the two entitlement test modules.


def sign_in(client, name, slug=None):
    return client.post(
        "/v1/session/resolve", json={"id_token": f"fake-token:{name}", "campaign": slug}
    )


def test_ana_is_recognised_claims_her_record_and_gets_the_grant(world, ent):
    body = sign_in(world, "ana", "founding").json()
    assert (body["access"]["tier"], body["join"]["recognition"], body["join"]["campaign"]) == (
        "paid",
        "paid",
        "founding",
    )
    assert body["join"]["grant"]["created"] is True and body["member"]["joined_via"] == "founding"
    assert body["member"]["email_hint"] == "a…@example.org" and "ana@" not in str(body)
    assert sorted(r["label"] for r in body["access"]["reasons"]) == [
        "launch_grant",
        "substack_subscription",
    ]
    again = sign_in(world, "ana").json()
    assert again["join"]["grant"] is None and again["member"]["joined_via"] == "founding"
    assert ent.store.get_campaign("founding").counts["arrivals"] == 1


def test_the_grant_does_not_depend_on_the_link(world):
    assert sign_in(world, "ana", None).json()["join"]["grant"]["created"] is True


def test_bo_and_hal_are_free_and_hal_sees_his_plan(world):
    assert sign_in(world, "bo", "founding").json()["access"]["tier"] == "free"
    hal = sign_in(world, "hal").json()
    assert (
        hal["access"]["tier"] == "free"
        and hal["join"]["grant"] is None
        and hal["join"]["recognition"] == "paid"
    )
    assert [(r["label"], r["plan_interval"]) for r in hal["access"]["reasons"]] == [
        ("substack_status", "month")
    ]


def test_a_bad_token_and_an_unverified_address_are_refused(world, idn):
    assert (
        world.post(
            "/v1/session/resolve", json={"id_token": "garbage", "campaign": None}
        ).status_code
        == 401
    )
    idn.provider.unverified.add("bo")
    assert sign_in(world, "bo").status_code == 401


def test_a_closed_join_refuses_new_people_and_admits_members(world, ent):
    sign_in(world, "ana")
    ent.store.put_launch_config(TERMS.model_copy(update={"join_open": False}))
    assert sign_in(world, "ana").status_code == 200
    r = sign_in(world, "bo")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_member_routes_need_a_good_cookie(world, idn):
    cookie = sign_in(world, "ana").json()["session"]["cookie"]
    assert world.get("/v1/me", headers={"X-Member-Session": cookie}).status_code == 200
    for bad in ({}, {"X-Member-Session": "garbage"}, {"X-Member-Session": cookie + "x"}):
        r = world.get("/v1/me", headers=bad)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    world.post("/v1/session/revoke", headers={"X-Member-Session": cookie})
    assert world.get("/v1/me", headers={"X-Member-Session": cookie}).status_code == 401


def test_terms_gate_every_member_route_except_the_four(world):
    cookie = {"X-Member-Session": sign_in(world, "ana").json()["session"]["cookie"]}
    assert world.get("/v1/me", headers=cookie).json()["member"]["terms"]["accepted"] is False
    gated = world.get("/v1/me/entitlements", headers=cookie)
    assert gated.status_code == 409 and gated.json()["error"]["code"] == "terms_required"
    assert (
        world.post(
            "/v1/me/terms-acceptance",
            headers=cookie,
            json={"terms_version": "old", "privacy_version": "p1"},
        ).status_code
        == 422
    )
    ok = world.post(
        "/v1/me/terms-acceptance",
        headers=cookie,
        json={"terms_version": "t1", "privacy_version": "p1"},
    )
    assert ok.json()["member"]["terms"]["accepted"] is True
    assert world.get("/v1/me/entitlements", headers=cookie).status_code == 200


def test_a_new_required_version_asks_again(world, ent):
    cookie = {"X-Member-Session": sign_in(world, "ana").json()["session"]["cookie"]}
    world.post(
        "/v1/me/terms-acceptance",
        headers=cookie,
        json={"terms_version": "t1", "privacy_version": "p1"},
    )
    ent.store.put_launch_config(TERMS.model_copy(update={"required_terms_version": "t2"}))
    assert world.get("/v1/me", headers=cookie).json()["member"]["terms"]["accepted"] is False


def test_a_deletion_request_ends_the_sessions_and_blocks_sign_in(world):
    cookie = {"X-Member-Session": sign_in(world, "bo").json()["session"]["cookie"]}
    assert world.post("/v1/me/deletion-request", headers=cookie).json() == {
        "status": "deletion_requested"
    }
    assert (
        world.get("/v1/me", headers=cookie).status_code == 401
        and sign_in(world, "bo").status_code == 401
    )


def test_a_stale_reconcile_starts_a_check_when_the_port_exists(world, idn):
    calls = []
    idn.request_refresh = lambda uid, now: calls.append(uid) or "started"
    idn.last_reconcile_at = lambda: T0 - timedelta(hours=2)
    assert sign_in(world, "bo").json()["join"]["check"] == "started" and calls == ["u-bo"]
    idn.last_reconcile_at = lambda: T0
    assert sign_in(world, "bo").json()["join"]["check"] == "fresh" and calls == ["u-bo"]


def test_no_address_reaches_the_log_or_an_event(world, ent, caplog):
    with caplog.at_level(logging.DEBUG):
        sign_in(world, "ana", "founding")
        world.post("/v1/session/resolve", json={"id_token": "fake-token:nobody", "campaign": None})
    assert "@" not in caplog.text and all("@" not in e.model_dump_json() for e in ent.bus.published)


# Added by the controller's rulings for this task.


def test_a_cookie_of_a_deleted_or_missing_member_is_refused_on_every_route(world, idn):
    from platform_api.identity.store import InMemoryMemberStore

    cookie = {"X-Member-Session": sign_in(world, "ana").json()["session"]["cookie"]}
    world.post(
        "/v1/me/terms-acceptance",
        headers=cookie,
        json={"terms_version": "t1", "privacy_version": "p1"},
    )
    held = idn.members.get("u-ana")
    idn.members.put(held.model_copy(update={"status": "deletion_requested"}))
    for method, path in (
        ("GET", "/v1/me"),
        ("GET", "/v1/me/entitlements"),
        ("POST", "/v1/session/revoke"),
    ):
        r = world.request(method, path, headers=cookie)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    idn.members = InMemoryMemberStore()
    assert world.get("/v1/me", headers=cookie).status_code == 401


def test_a_returning_member_who_gains_a_grant_at_sign_in_gets_one_tier_event(world, ent):
    from tests.entitlements.test_campaigns import campaign
    from tests.entitlements.test_reconcile import run, state

    assert sign_in(world, "bo").json()["access"]["tier"] == "free"
    ent.store.put_campaigns([campaign(opens_at=T0 + timedelta(days=1))])  # not open yet
    run(ent, [state("bo", "sub_b", grant="status:substack_paid")], run_id="r2")
    assert not any(e.type.endswith("membership.tier.changed") for e in ent.bus.published)
    ent.store.put_campaigns([campaign()])  # now open: the grant is due at the next sign-in
    ent.bus.published.clear()
    body = sign_in(world, "bo").json()
    assert body["access"]["tier"] == "paid" and body["join"]["grant"]["created"] is True
    changed = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert [
        (e.data["member_uid"], e.data["from"], e.data["to"], e.data["run_id"], e.data["reason"])
        for e in changed
    ] == [("u-bo", "free", "paid", "session", "sign_in")]
    assert not any(e.type.endswith("membership.member.registered") for e in ent.bus.published)


def test_a_new_member_gets_registered_and_no_tier_event(world, ent):
    ent.bus.published.clear()
    sign_in(world, "ana", "founding")
    types = [e.type.removeprefix("org.audhdneurobiology.") for e in ent.bus.published]
    assert "membership.member.registered" in types and "membership.tier.changed" not in types
    [registered] = [e for e in ent.bus.published if e.type.endswith("membership.member.registered")]
    assert registered.data["member_uid"] == "u-ana" and registered.data["campaign"] == "founding"


def test_two_first_sign_ins_at_once_create_one_member(world, idn, ent):
    from platform_api.identity.store import InMemoryMemberStore

    class OtherSignInWins(InMemoryMemberStore):
        def create_if_absent(self, member):
            super().create_if_absent(member.model_copy(update={"joined_via": "members"}))
            return super().create_if_absent(member)

    idn.members = OtherSignInWins()
    body = sign_in(world, "ana", "founding")
    assert body.status_code == 200 and body.json()["member"]["joined_via"] == "members"
    assert idn.members.count() == 1
    assert not [e for e in ent.bus.published if e.type.endswith("member.registered")]
    assert ent.store.get_campaign("founding").counts.get("arrivals", 0) == 0


def test_a_member_is_created_only_when_absent(idn):
    from platform_api.identity.models import Member

    member = Member(
        uid="u-ana",
        primary_contact_id="c1",
        linked_contact_ids=[],
        email="ana@example.org",
        display_name=None,
        terms_accepted=None,
        joined_via=None,
        status="active",
        created_at=T0,
        last_seen_at=T0,
    )
    assert idn.members.create_if_absent(member) is True
    assert idn.members.create_if_absent(member.model_copy(update={"joined_via": "x"})) is False
    assert idn.members.get("u-ana") == member


def _land_during_the_sign_in(monkeypatch, idn, act):
    """`act(uid)` runs right after the sign-in has read the member, before it writes."""
    members = idn.members
    get = members.get

    def read_then_act(uid):
        found = get(uid)
        monkeypatch.setattr(members, "get", get)
        act(uid)
        return found

    monkeypatch.setattr(members, "get", read_then_act)


def test_a_deletion_that_lands_during_a_sign_in_stands_and_no_cookie_is_issued(
    world, idn, monkeypatch
):
    from platform_api.identity import public as identity

    sign_in(world, "bo")
    _land_during_the_sign_in(monkeypatch, idn, lambda uid: identity.request_deletion(uid, T0))
    issued = idn.provider._count
    r = sign_in(world, "bo")
    assert r.status_code == 401 and "session" not in r.json()
    stored = idn.members.get("u-bo")
    assert (stored.status, stored.deletion_requested_at) == ("deletion_requested", T0)
    assert idn.provider._count == issued


def test_terms_accepted_during_a_sign_in_are_kept(world, idn, monkeypatch):
    from platform_api.identity import public as identity

    sign_in(world, "ana")
    _land_during_the_sign_in(
        monkeypatch, idn, lambda uid: identity.accept_terms(uid, "t1", "p1", T0)
    )
    r = sign_in(world, "ana")
    assert r.status_code == 200 and r.json()["member"]["terms"]["accepted"] is True
    assert idn.members.get("u-ana").terms_accepted.terms_version == "t1"


def test_a_token_the_provider_will_not_turn_into_a_cookie_is_refused(world, idn, monkeypatch):
    from platform_api.identity.provider import InvalidToken

    def refuse(id_token, ttl):
        raise InvalidToken("the sign-in token was refused")

    monkeypatch.setattr(idn.provider, "create_session_cookie", refuse)
    r = sign_in(world, "ana")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_a_member_removed_after_the_session_check_is_unauthenticated(world, idn):
    from platform_api.identity.models import MemberRef

    world.app.state.member_from_session = lambda cookie: MemberRef(uid="u-gone", terms_ok=True)
    cookie = {"X-Member-Session": "anything"}
    for method, path, body in (
        ("GET", "/v1/me", None),
        ("POST", "/v1/me/terms-acceptance", {"terms_version": "t1", "privacy_version": "p1"}),
        ("POST", "/v1/me/deletion-request", None),
    ):
        r = world.request(method, path, headers=cookie, json=body)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
