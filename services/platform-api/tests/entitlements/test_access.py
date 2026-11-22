from datetime import timedelta

import pytest

from platform_api.entitlements.access import access_from, decision_for, is_live, label_for
from tests.fixtures.people import T0, holdings, record


@pytest.mark.parametrize(
    ("name", "tier"),
    [
        ("ana", "paid"),
        ("bo", "free"),
        ("cy", "free"),
        ("di", "free"),
        ("fay", "paid"),
        ("gus", "paid"),
        ("hal", "free"),
    ],
)
def test_tiers_of_the_fixture_people(name, tier):
    assert access_from(holdings(name), T0).tier == tier


def test_sections_follow_the_tier():
    assert access_from([], T0).sections == ["overview", "library", "account"]
    assert "research" in access_from(holdings("ana"), T0).sections


def test_a_status_grant_unlocks_nothing_and_is_explained():
    access = access_from(holdings("hal"), T0)
    assert (access.tier, access.items) == ("free", [])
    assert [(r.label, r.plan_interval, r.status) for r in access.reasons] == [
        ("substack_status", "month", "active")
    ]


def test_a_grant_ends_on_its_date_without_waiting_for_a_sweep():
    grant = record("fay", "launch_grant", valid_until=T0 + timedelta(days=1))
    assert is_live(grant, T0) and not is_live(grant, T0 + timedelta(days=1))
    after = access_from([grant], T0 + timedelta(days=2))
    assert after.tier == "free" and [r.status for r in after.reasons] == ["expired"]


def test_a_source_backed_record_stays_live_past_its_date():
    assert is_live(record("ana", "stripe_year", valid_until=T0 - timedelta(days=3)), T0)


def test_grace_is_live_and_revoked_is_not():
    assert access_from([record("ana", "stripe_year", status="grace")], T0).tier == "paid"
    assert access_from([record("ana", "owner_grant", status="revoked")], T0).tier == "free"


def test_labels():
    assert [
        label_for(record("ana", k))
        for k in ("stripe_year", "launch_grant", "owner_grant", "roster_status", "item")
    ] == ["substack_subscription", "launch_grant", "owner_grant", "substack_status", "purchase"]


@pytest.mark.parametrize(
    ("holder", "item_access", "allowed", "reason"),
    [
        ("ana", "paid", True, None),
        ("bo", "paid", False, "paid_required"),
        ("bo", "free_members", True, None),
        ("ana", "purchase_only", False, "purchase_required"),
        ("buyer", "purchase_only", True, None),
        ("buyer", "paid", True, None),
    ],
)
def test_decisions(holder, item_access, allowed, reason):
    held = [record("bo", "item", grant="item:map-1")] if holder == "buyer" else holdings(holder)
    decision = decision_for(held, item_access, "map-1", T0)
    assert (decision.allowed, decision.reason) == (allowed, reason)


def test_access_for_joins_member_and_contact_records_once_and_can_open_needs_item_access(ent):
    from platform_api.entitlements import public
    from platform_api.entitlements.models import AuditEntry

    ana = record("ana", "owner_grant", member_uid="u-ana")
    audit = AuditEntry(
        at=T0,
        actor="owner:test",
        action="grant",
        subject=ana.entitlement_id,
        reason=None,
        evidence={},
    )
    ent.store.write(ana.contact_id, [ana], [audit])
    assert public.access_for("u-ana", T0).tier == "paid"
    assert public.can_open("u-ana", "map-1", T0, item_access="paid").allowed
    with pytest.raises(LookupError):
        public.can_open("u-ana", "map-1", T0)


def test_reasons_are_ordered_newest_end_last_and_name_the_campaign():
    soon = record("ana", "launch_grant", valid_until=T0 + timedelta(days=10))
    later = record("ana", "stripe_year")
    open_ended = record("ana", "owner_grant")
    access = access_from([open_ended, later, soon], T0)
    assert [r.valid_until for r in access.reasons] == [
        soon.valid_until,
        later.valid_until,
        None,
    ]
    by_label = {r.label: r.campaign for r in access.reasons}
    assert by_label["launch_grant"] == "founding"
    assert by_label["owner_grant"] is None
    assert by_label["substack_subscription"] is None
