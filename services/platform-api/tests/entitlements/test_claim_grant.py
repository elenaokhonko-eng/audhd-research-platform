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
    assert [e.type.rsplit(".", 3)[-3:] for e in ent.bus.published] == [
        ["membership", "entitlement", "granted"]
    ]


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
