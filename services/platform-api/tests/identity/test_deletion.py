import logging

import pytest

from platform_api.identity import public as identity
from tests.fixtures.people import EMAIL, T0
from tests.identity.test_sessions import sign_in

OWNER = "owner:acc-1"


def _sign_in_and_ask(world, idn, name):
    """Sign in, accept the terms, file a support request, then ask to be deleted."""
    cookie = {"X-Member-Session": sign_in(world, name, "founding").json()["session"]["cookie"]}
    world.post(
        "/v1/me/terms-acceptance",
        headers=cookie,
        json={"terms_version": "t1", "privacy_version": "p1"},
    )
    assert (
        world.post(
            "/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}
        ).status_code
        == 200
    )
    world.post("/v1/me/deletion-request", headers=cookie)
    return f"u-{name}"


def test_a_deleted_member_leaves_nothing_but_one_audit_entry(world, idn, ent):
    uid = _sign_in_and_ask(world, idn, "ana")
    [cid] = ent.store.contact_ids_for_member(uid)
    held = [e.entitlement_id for e in ent.store.entitlements_for_contacts([cid])]
    assert len(held) == 2  # her Substack record and her launch grant

    identity.delete_member(uid, OWNER, T0)

    assert ent.store.get_contact(cid) is None
    assert all(ent.store.get_entitlement(eid) is None for eid in held)
    assert idn.members.get(uid) is None
    assert [r for r in idn.members.support_requests() if r.member_uid == uid] == []
    assert idn.provider.deleted == [uid]
    [entry] = ent.store.audit_for(cid)
    assert (entry.action, entry.actor, entry.subject) == ("contact.forgotten", OWNER, cid)
    assert "@" not in entry.model_dump_json()


def test_the_same_address_signs_in_again_as_a_new_free_member(world, idn, ent):
    uid = _sign_in_and_ask(world, idn, "ana")
    identity.delete_member(uid, OWNER, T0)

    again = sign_in(world, "ana").json()
    assert again["member"]["uid"] != uid and again["access"]["tier"] == "free"
    new = idn.members.get(again["member"]["uid"])
    assert new is not None and new.status == "active" and new.created_at == T0
    from platform_api.entitlements import public as ent_api

    assert ent.store.contact_ids_for_member(new.uid) == [ent_api.contact_id_for(EMAIL["ana"])]


def test_a_member_who_did_not_ask_cannot_be_deleted(world, idn, ent):
    sign_in(world, "bo")
    with pytest.raises(ValueError) as err:
        identity.delete_member("u-bo", OWNER, T0)
    assert "@" not in str(err.value)
    assert idn.members.get("u-bo") is not None and ent.store.contact_ids_for_member("u-bo")
    assert idn.provider.deleted == []


def test_a_second_delete_is_harmless(world, idn, ent):
    uid = _sign_in_and_ask(world, idn, "bo")
    [cid] = ent.store.contact_ids_for_member(uid)
    identity.delete_member(uid, OWNER, T0)
    identity.delete_member(uid, OWNER, T0)
    assert idn.members.get(uid) is None and ent.store.get_contact(cid) is None
    assert len(ent.store.audit_for(cid)) == 1
    assert identity.pending_deletions() == []
    assert idn.provider.deleted == [uid]  # an absent member means the deletion is complete


def test_records_that_name_the_member_hold_no_address_and_are_left_to_expire(world, idn, ent):
    uid = _sign_in_and_ask(world, idn, "ana")
    [cid] = ent.store.contact_ids_for_member(uid)
    claimed = [e.entitlement_id for e in ent.store.entitlements_for_contacts([cid])]
    before = [entry for eid in claimed for entry in ent.store.audit_for(eid)]
    assert before

    identity.delete_member(uid, OWNER, T0)

    after = [entry for eid in claimed for entry in ent.store.audit_for(eid)]
    assert after == before  # kept, to expire with the audit log
    assert all("@" not in entry.model_dump_json() for entry in after)


# Added by the controller's rulings for this task.


def test_only_requests_are_pending_and_oldest_first(world, idn, ent):
    from datetime import timedelta

    for name in ("ana", "bo", "cy"):
        sign_in(world, name)
    identity.request_deletion("u-cy", T0 - timedelta(days=2))
    identity.request_deletion("u-ana", T0)
    pending = identity.pending_deletions()
    assert [(r.uid, r.requested_at) for r in pending] == [
        ("u-cy", T0 - timedelta(days=2)),
        ("u-ana", T0),
    ]


def test_a_contact_another_member_owns_survives_the_delete(world, idn, ent):
    from platform_api.entitlements.models import ChannelsPatch
    from platform_api.entitlements.public import upsert_contact

    uid = _sign_in_and_ask(world, idn, "bo")
    sign_in(world, "cy")
    [cy_contact] = ent.store.contact_ids_for_member("u-cy")
    unowned = upsert_contact(EMAIL["di"], ChannelsPatch())
    held = idn.members.get(uid)
    idn.members.put(
        held.model_copy(update={"primary_contact_id": cy_contact, "linked_contact_ids": [unowned]})
    )

    identity.delete_member(uid, OWNER, T0)

    assert ent.store.get_contact(cy_contact) is not None
    assert ent.store.get_contact(unowned) is not None
    assert ent.store.audit_for(cy_contact) == [] and ent.store.audit_for(unowned) == []
    assert idn.members.get("u-cy") is not None


def test_nothing_in_the_deletion_path_logs_or_returns_an_address(world, idn, ent, caplog):
    uid = _sign_in_and_ask(world, idn, "ana")
    with caplog.at_level(logging.DEBUG):
        pending = identity.pending_deletions()
        result = identity.delete_member(uid, OWNER, T0)
        identity.delete_member(uid, OWNER, T0)
        sign_in(world, "bo")
        with pytest.raises(ValueError) as err:
            identity.delete_member("u-bo", OWNER, T0)
    assert result is None and "@" not in str(err.value)
    assert all("@" not in r.model_dump_json() for r in pending)
    assert "@" not in caplog.text
    assert all("@" not in e.model_dump_json() for e in ent.bus.published)


# Added by the coordinator's ruling on the order of removal: the member record goes last.


def test_a_sign_in_during_the_gap_before_the_record_is_deleted_is_refused(world, idn, ent):
    uid = _sign_in_and_ask(world, idn, "ana")
    old_token = f"fake-token:ana:{uid}"  # a token of the account about to be deleted
    delete = idn.members.delete
    during = []

    def delete_after_a_sign_in(target):
        from platform_api.identity.provider import InvalidToken

        held = idn.members.get(target)
        r = world.post("/v1/session/resolve", json={"id_token": old_token, "campaign": None})
        try:
            idn.provider.verify_id_token(old_token)
            provider_refused = False
        except InvalidToken:
            provider_refused = True
        during.append((r.status_code, held is not None and held.status, provider_refused))
        return delete(target)

    idn.members.delete = delete_after_a_sign_in
    assert idn.provider.verify_id_token(old_token).uid == uid  # accepted before the delete
    identity.delete_member(uid, OWNER, T0)
    assert during == [(401, "deletion_requested", True)]
    assert idn.provider.deleted == [uid] and idn.members.get(uid) is None


def test_a_failed_provider_step_keeps_the_record_for_a_retry(world, idn, ent):
    from platform_api.identity.provider import ProviderError

    uid = _sign_in_and_ask(world, idn, "ana")
    [cid] = ent.store.contact_ids_for_member(uid)
    real = idn.provider.delete_user

    def fails(target):
        raise ProviderError("the sign-in account could not be deleted")

    idn.provider.delete_user = fails
    with pytest.raises(ProviderError):
        identity.delete_member(uid, OWNER, T0)
    held = idn.members.get(uid)
    assert held is not None and held.status == "deletion_requested"
    assert ent.store.get_contact(cid) is None
    assert [r for r in idn.members.support_requests() if r.member_uid == uid] == []
    assert [r.uid for r in identity.pending_deletions()] == [uid]

    idn.provider.delete_user = real
    identity.delete_member(uid, OWNER, T0)
    assert idn.members.get(uid) is None and idn.provider.deleted == [uid]
    assert len(ent.store.audit_for(cid)) == 1
