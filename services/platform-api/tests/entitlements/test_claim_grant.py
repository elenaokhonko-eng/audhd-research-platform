from datetime import timedelta

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import ChannelsPatch
from tests.fixtures.people import EMAIL, T0, record


def seeded(runtime, name, *kinds):
    cid = ent_api.upsert_contact(EMAIL[name], ChannelsPatch())
    runtime.store.write(cid, [record(name, k, contact_id=cid) for k in kinds], [])
    return cid


def test_first_sign_in_claims_what_was_waiting(ent):
    cid = seeded(ent, "ana", "stripe_year")
    claimed = ent_api.claim_for_member("u-ana", cid)
    assert len(claimed) == 1 and ent.store.get_entitlement(claimed[0]).member_uid == "u-ana"
    assert ent_api.claim_for_member("u-ana", cid) == []
    assert ent_api.access_for("u-ana", T0).tier == "paid"
    assert [a.action for a in ent.store.audit_for(claimed[0])] == ["entitlement.claimed"]
    assert len(ent_api.access_for("u-ana", T0).reasons) == 1


def test_a_claim_sticks_and_cannot_be_taken(ent):
    cid = seeded(ent, "ana", "stripe_year")
    ent_api.claim_for_member("u-ana", cid)
    assert ent_api.claim_for_member("u-other", cid) == []
    assert ent.store.entitlements_for_member("u-other") == []


def test_an_owner_grant_is_live_until_its_date_and_is_audited(ent):
    cid = seeded(ent, "di")
    ent_api.claim_for_member("u-di", cid)
    eid = ent_api.grant(
        cid,
        "tier:paid",
        T0 + timedelta(days=30),
        "complimentary reader, reviewed",
        "owner:acc-1",
        T0,
    )
    assert ent_api.access_for("u-di", T0).tier == "paid"
    assert ent_api.access_for("u-di", T0 + timedelta(days=31)).tier == "free"
    entry = ent.store.audit_for(eid)[-1]
    assert (entry.action, entry.actor, entry.reason) == (
        "entitlement.granted",
        "owner:acc-1",
        "complimentary reader, reviewed",
    )
    kinds = [e.type.removeprefix("org.audhdneurobiology.") for e in ent.bus.published]
    assert kinds == ["membership.entitlement.granted", "membership.tier.changed"]
    granted = ent.bus.published[0]
    assert granted.subject == cid
    ref = ent.store.get_entitlement(eid).source_ref
    assert granted.data == {
        "contact_id": cid,
        "entitlement_id": eid,
        "grant": "tier:paid",
        "source": "grant",
        "source_ref": ref,
        "access_scope": "platform_only",
    }
    assert ent.store.get_entitlement(eid).member_uid == "u-di"


@pytest.mark.parametrize(
    ("grant", "until", "reason"),
    [
        ("tier:paid", T0 + timedelta(days=1), ""),
        ("status:substack_paid", T0 + timedelta(days=1), "r"),
        ("tier:paid", T0, "r"),
    ],
)
def test_a_grant_without_reason_with_a_wrong_name_or_already_over_is_refused(
    ent, grant, until, reason
):
    with pytest.raises(ValueError):
        ent_api.grant(seeded(ent, "di"), grant, until, reason, "owner:acc-1", T0)


def test_only_grants_can_be_revoked(ent):
    cid = seeded(ent, "ana", "stripe_year")
    eid = ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    ent_api.revoke(eid, "mistake", "owner:acc-1", T0)
    assert ent.store.get_entitlement(eid).status == "revoked"
    stripe_id = ent.store.entitlements_by_source("substack_stripe")[0].entitlement_id
    with pytest.raises(ValueError):
        ent_api.revoke(stripe_id, "no", "owner:acc-1", T0)
    with pytest.raises(LookupError):
        ent_api.revoke("nope", "no", "owner:acc-1", T0)


def test_a_grant_for_an_unknown_contact_is_refused_and_leaves_no_trace(ent):
    with pytest.raises(LookupError):
        ent_api.grant("no-such-contact", "tier:paid", None, "r", "owner:acc-1", T0)
    assert ent.store.entitlements_by_source("grant") == []
    assert ent.store.audit_for("no-such-contact") == []
    assert ent.bus.published == []


def _types(ent):
    return [e.type.removeprefix("org.audhdneurobiology.") for e in ent.bus.published]


def test_revoke_is_audited_and_announced(ent):
    cid = seeded(ent, "ana", "stripe_year")
    eid = ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    ent.bus.published.clear()
    ent_api.revoke(eid, "mistake", "owner:acc-1", T0)
    entry = ent.store.audit_for(eid)[-1]
    assert (entry.action, entry.actor, entry.reason) == (
        "entitlement.revoked",
        "owner:acc-1",
        "mistake",
    )
    (event,) = ent.bus.published
    assert event.type.endswith("membership.entitlement.ended")
    assert event.data == {
        "entitlement_id": eid,
        "contact_id": cid,
        "status": "revoked",
        "reason": "revoked",
    }


def test_a_claim_cannot_be_overwritten_or_read_across_members(ent):
    cid = seeded(ent, "ana", "stripe_year")
    ent_api.claim_for_member("u-A", cid)
    ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-B", "x": "1"}))
    contact = ent.store.get_contact(cid)
    assert contact.channels["platform"]["member_uid"] == "u-A"
    assert contact.channels["platform"]["x"] == "1"
    ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-A"}))
    assert ent.store.get_contact(cid).channels["platform"]["member_uid"] == "u-A"
    assert ent_api.access_for("u-B", T0).tier == "free"


def test_a_contact_re_owned_in_the_store_does_not_leak_records(ent):
    cid = seeded(ent, "ana", "stripe_year")
    ent_api.claim_for_member("u-A", cid)
    contact = ent.store.get_contact(cid)
    platform = {**contact.channels["platform"], "member_uid": "u-B"}
    ent.store.put_contact(contact.model_copy(update={"channels": {"platform": platform}}))
    access = ent_api.access_for("u-B", T0)
    assert access.tier == "free" and access.reasons == []


def test_an_unclaimed_record_added_later_is_not_taken_by_another_member(ent):
    cid = seeded(ent, "ana", "stripe_year")
    ent_api.claim_for_member("u-A", cid)
    ent.store.write(cid, [record("ana", "item", contact_id=cid)], [])
    assert ent_api.claim_for_member("u-B", cid) == []


def test_owner_grant_and_revoke_publish_tier_changes_for_a_member(ent):
    cid = seeded(ent, "di")
    ent_api.claim_for_member("u-di", cid)
    eid = ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    changed = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert len(changed) == 1
    assert (changed[0].data["member_uid"], changed[0].data["from"], changed[0].data["to"]) == (
        "u-di",
        "free",
        "paid",
    )
    ent.bus.published.clear()
    ent_api.revoke(eid, "r", "owner:acc-1", T0)
    changed = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert len(changed) == 1
    assert (changed[0].data["from"], changed[0].data["to"]) == ("paid", "free")


def test_a_grant_to_a_contact_without_a_member_changes_no_tier(ent):
    cid = seeded(ent, "bo")
    ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    assert _types(ent) == ["membership.entitlement.granted"]


def test_revoke_needs_a_reason(ent):
    cid = seeded(ent, "ana")
    eid = ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    with pytest.raises(ValueError):
        ent_api.revoke(eid, "  ", "owner:acc-1", T0)
    assert ent.store.get_entitlement(eid).status == "active"


def test_a_reason_with_an_address_is_refused_without_repeating_it(ent):
    cid = seeded(ent, "ana")
    bad = "because " + EMAIL["bo"]
    with pytest.raises(ValueError) as grant_err:
        ent_api.grant(cid, "tier:paid", None, bad, "owner:acc-1", T0)
    assert EMAIL["bo"] not in str(grant_err.value)
    eid = ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    with pytest.raises(ValueError) as revoke_err:
        ent_api.revoke(eid, bad, "owner:acc-1", T0)
    assert EMAIL["bo"] not in str(revoke_err.value)
    assert ent.store.get_entitlement(eid).status == "active"


@pytest.mark.parametrize("name", ["tier:", "tier:gold", "item:", "item:  "])
def test_a_grant_names_the_paid_tier_or_a_real_item(ent, name):
    with pytest.raises(ValueError):
        ent_api.grant(seeded(ent, "di"), name, None, "r", "owner:acc-1", T0)


def test_a_grant_may_name_an_item(ent):
    cid = seeded(ent, "di")
    assert ent_api.grant(cid, "item:sample", None, "r", "owner:acc-1", T0)
