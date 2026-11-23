import logging

from tests.identity.test_sessions import sign_in


def member(world, name="ed"):
    cookie = {"X-Member-Session": sign_in(world, name).json()["session"]["cookie"]}
    world.post(
        "/v1/me/terms-acceptance",
        headers=cookie,
        json={"terms_version": "t1", "privacy_version": "p1"},
    )
    return cookie


def test_a_note_is_stored_and_never_copied(world, idn, ent, caplog):
    cookie = member(world)
    with caplog.at_level(logging.DEBUG):
        r = world.post(
            "/v1/me/support-requests",
            headers=cookie,
            json={"kind": "paid_not_recognised", "note": "I pay with another address"},
        )
    assert r.status_code == 200 and r.json()["id"]
    assert [s.note for s in idn.members.support_requests()] == ["I pay with another address"]
    assert "another address" not in caplog.text
    [event] = [e for e in ent.bus.published if e.type.endswith("membership.support.requested")]
    assert event.data == {"member_uid": "u-ed", "kind": "paid_not_recognised"}


def test_a_long_note_and_an_unknown_kind_are_refused(world):
    cookie = member(world)
    assert (
        world.post(
            "/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "x" * 501}
        ).status_code
        == 422
    )
    assert (
        world.post(
            "/v1/me/support-requests", headers=cookie, json={"kind": "refund", "note": "x"}
        ).status_code
        == 422
    )


def test_the_sixth_request_in_a_day_is_limited(world):
    cookie = member(world)
    codes = [
        world.post(
            "/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}
        ).status_code
        for _ in range(6)
    ]
    assert codes == [200] * 5 + [429]
    last = world.post(
        "/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}
    ).json()
    assert last["error"]["code"] == "rate_limited" and last["error"]["retry_after"] > 0


def test_the_request_needs_accepted_terms(world):
    cookie = {"X-Member-Session": sign_in(world, "ed").json()["session"]["cookie"]}
    assert (
        world.post(
            "/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}
        ).status_code
        == 409
    )
