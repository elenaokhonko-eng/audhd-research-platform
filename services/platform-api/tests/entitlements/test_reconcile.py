from datetime import timedelta

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import (
    Campaign,
    ChannelsPatch,
    GrantPolicy,
    LaunchConfig,
    SourceState,
)
from platform_api.entitlements.reconcile import Guard
from tests.fixtures.people import CUT_OFF, EMAIL, T0


def state(
    name,
    ref,
    status="active",
    grant="tier:paid",
    interval="year",
    email=None,
    source="substack_stripe",
):
    return SourceState(
        source=source,
        source_ref=ref,
        email=email or EMAIL[name],
        grant=grant,
        status=status,
        started_at=T0 - timedelta(days=200),
        valid_until=T0 + timedelta(days=165),
        plan_interval=interval,
        access_scope="substack+platform",
        provider_time=T0,
    )


def run(ent, states, guard=None, run_id="r1"):
    existing = ent.store.entitlements_by_source("substack_stripe")
    plan = ent_api.plan_reconcile(existing, states, guard or Guard(), T0)
    return plan, ent_api.apply_plan(plan, run_id, T0)


def test_first_run_creates_and_second_run_changes_nothing(ent):
    states = [
        state("ana", "sub_a"),
        state("hal", "sub_h", grant="status:substack_paid", interval="month"),
    ]
    _, first = run(ent, states)
    plan, second = run(ent, states, run_id="r2")
    assert (first.created, second.created, second.updated, second.ended, second.unchanged) == (
        2,
        0,
        0,
        0,
        2,
    )
    record = ent.store.entitlements_by_source("substack_stripe")[0]
    assert record.valid_from == T0 - timedelta(days=200) and record.member_uid is None


def test_an_expired_state_ends_only_its_own_record(ent):
    run(ent, [state("fay", "sub_f"), state("ana", "sub_a")])
    cid = ent_api.contact_id_for(EMAIL["fay"])
    ent_api.grant(cid, "tier:paid", T0 + timedelta(days=90), "launch", "owner:acc-1", T0)
    _, report = run(
        ent, [state("fay", "sub_f", status="expired"), state("ana", "sub_a")], run_id="r2"
    )
    by_source = {e.source: e.status for e in ent.store.entitlements_for_contacts([cid])}
    assert report.ended == 1 and by_source == {"substack_stripe": "expired", "grant": "active"}


def test_a_record_the_source_did_not_mention_is_left_alone_and_reported(ent):
    run(ent, [state("ana", "sub_a"), state("gus", "sub_g")])
    plan, report = run(ent, [state("ana", "sub_a")], run_id="r2")
    assert (report.ended, report.unseen, len(plan.unseen)) == (0, 1, 1)
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_the_guard_blocks_a_run_that_would_end_too_many(ent):
    names = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]
    run(ent, [state(n, f"sub_{n}") for n in names])
    plan, report = run(
        ent, [state(n, f"sub_{n}", status="expired") for n in names[:6]], run_id="r2"
    )
    assert plan.blocked and plan.actions == [] and (plan.ends, plan.live_before) == (6, 8)
    assert report.blocked and report.ended == 0
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_five_ends_are_allowed(ent):
    names = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]
    run(ent, [state(n, f"sub_{n}") for n in names])
    plan, report = run(
        ent, [state(n, f"sub_{n}", status="expired") for n in names[:5]], run_id="r2"
    )
    assert not plan.blocked and report.ended == 5


def test_a_tier_change_is_one_event_for_a_member_and_none_for_a_stranger(ent):
    run(ent, [state("ana", "sub_a"), state("bo", "sub_b")])
    ent_api.claim_for_member("u-ana", ent_api.contact_id_for(EMAIL["ana"]))
    ent.bus.published.clear()
    run(
        ent,
        [state("ana", "sub_a", status="expired"), state("bo", "sub_b", status="expired")],
        run_id="r2",
    )
    changed = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert [(e.data["member_uid"], e.data["from"], e.data["to"]) for e in changed] == [
        ("u-ana", "paid", "free")
    ]


def test_an_address_changed_at_the_source_moves_an_unclaimed_record(ent):
    run(ent, [state("ed", "sub_e")])
    _, report = run(ent, [state("ed", "sub_e", email="ed.other@example.org")], run_id="r2")
    old = ent.store.entitlements_for_contacts([ent_api.contact_id_for(EMAIL["ed"])])
    new = ent.store.entitlements_for_contacts([ent_api.contact_id_for("ed.other@example.org")])
    assert (
        (report.moved, report.ended) == (1, 0)
        and [e.status for e in old] == ["expired"]
        and [e.status for e in new] == ["active"]
    )


def test_a_claimed_record_stays_with_its_member_when_the_address_changes(ent):
    run(ent, [state("ana", "sub_a")])
    cid = ent_api.contact_id_for(EMAIL["ana"])
    ent_api.claim_for_member("u-ana", cid)
    _, report = run(
        ent, [state("ana", "sub_a", email="ana.new@example.org", status="grace")], run_id="r2"
    )
    kept = ent.store.entitlements_for_member("u-ana")
    assert (report.moved, report.updated) == (0, 1) and [
        (e.contact_id, e.status) for e in kept
    ] == [(cid, "grace")]


def test_a_reactivated_subscription_becomes_active_again(ent):
    run(ent, [state("ana", "sub_a")])
    run(ent, [state("ana", "sub_a", status="expired")], run_id="r2")
    _, report = run(ent, [state("ana", "sub_a")], run_id="r3")
    assert (
        report.updated == 1
        and ent.store.entitlements_by_source("substack_stripe")[0].status == "active"
    )


def test_the_same_reference_twice_in_one_run_is_refused(ent):
    with pytest.raises(ValueError, match="sub_a"):
        ent_api.plan_reconcile([], [state("ana", "sub_a"), state("bo", "sub_a")], Guard(), T0)


def test_a_plan_and_a_report_never_print_an_address(ent):
    plan = ent_api.plan_reconcile([], [state("ana", "sub_a")], Guard(), T0)
    assert "@" not in repr(plan) and "@" not in ent_api.apply_plan(plan, "r1", T0).model_dump_json()


# Controller rulings, pinned.


def test_a_move_creates_the_new_record_before_it_ends_the_old_one(ent):
    run(ent, [state("ed", "sub_e")])
    writes = []
    store_write = ent.store.write

    def spy(contact_id, entitlements, audit):
        writes.append([(e.contact_id, e.status) for e in entitlements])
        store_write(contact_id, entitlements, audit)

    ent.store.write = spy
    plan, report = run(ent, [state("ed", "sub_e", email="ed.other@example.org")], run_id="r2")
    old_cid, new_cid = (
        ent_api.contact_id_for(EMAIL["ed"]),
        ent_api.contact_id_for("ed.other@example.org"),
    )
    assert [a.kind for a in plan.actions] == ["move", "move"] and report.moved == 1
    assert writes == [[(new_cid, "active")], [(old_cid, "expired")]]
    [new] = ent.store.entitlements_for_contacts([new_cid])
    [entry] = ent.store.audit_for(new.entitlement_id)
    assert (entry.actor, new.updated_by) == ("run:r2", "run:r2") and "moved_from" in entry.evidence


def test_a_tier_change_from_a_run_carries_exactly_the_agreed_data(ent):
    run(ent, [state("ana", "sub_a")])
    cid = ent_api.contact_id_for(EMAIL["ana"])
    ent_api.claim_for_member("u-ana", cid)
    ent.bus.published.clear()
    _, report = run(ent, [state("ana", "sub_a", status="expired")], run_id="r7")
    [event] = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert report.tier_changes == 1
    assert event.data == {
        "member_uid": "u-ana",
        "contact_id": cid,
        "from": "paid",
        "to": "free",
        "reason": "reconcile",
        "run_id": "r7",
    }


def test_too_many_moves_between_contacts_block_the_plan(ent):
    names = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]
    run(ent, [state(n, f"sub_{n}") for n in names])
    moved = [state(n, f"sub_{n}", email=f"{n}.other@example.org") for n in names[:6]]
    plan, report = run(ent, moved + [state(n, f"sub_{n}") for n in names[6:]], run_id="r2")
    assert plan.blocked and plan.actions == [] and plan.ends == 0
    assert (report.blocked, report.moved) == (True, 0)
    assert (
        ent.store.entitlements_for_contacts([ent_api.contact_id_for("ana.other@example.org")]) == []
    )
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_a_renamed_grant_under_a_claimed_contact_ends_the_old_record_and_creates_the_new(ent):
    run(ent, [state("ana", "sub_a")])
    cid = ent_api.contact_id_for(EMAIL["ana"])
    ent_api.claim_for_member("u-ana", cid)
    _, report = run(ent, [state("ana", "sub_a", grant="status:substack_paid")], run_id="r2")
    held = sorted(
        (e.contact_id, e.grant, e.status, e.member_uid)
        for e in ent.store.entitlements_for_member("u-ana")
    )
    assert (report.moved, report.ended, report.created) == (1, 0, 0)
    assert held == [
        (cid, "status:substack_paid", "active", "u-ana"),
        (cid, "tier:paid", "expired", "u-ana"),
    ]


def test_a_revoked_record_is_never_changed_by_a_plan(ent):
    run(ent, [state("ana", "sub_a")])
    [record] = ent.store.entitlements_by_source("substack_stripe")
    revoked = record.model_copy(update={"status": "revoked"})
    ent.store.write(record.contact_id, [revoked], [])
    for i, status in enumerate(["active", "expired", "grace"]):
        plan, report = run(
            ent, [state("ana", "sub_a", status=status, interval="month")], run_id=f"r{i + 2}"
        )
        assert plan.actions == [] and (report.unchanged, report.unseen) == (1, 0)
    assert ent.store.entitlements_by_source("substack_stripe") == [revoked]


# A run follows the live record of a moved subscription.


def live_for(ent, ref):
    return [
        e
        for e in ent.store.entitlements_by_source("substack_stripe")
        if e.source_ref == ref and e.status in ("active", "grace")
    ]


def test_an_address_that_changes_back_leaves_no_paid_record_behind(ent):
    other = "ed.other@example.org"
    run(ent, [state("ed", "sub_e")])
    run(ent, [state("ed", "sub_e", email=other)], run_id="r2")
    plan, _ = run(ent, [state("ed", "sub_e")], run_id="r3")
    assert plan.unseen == [] and len(live_for(ent, "sub_e")) == 1
    run(ent, [state("ed", "sub_e", status="expired")], run_id="r4")
    assert [e for e in live_for(ent, "sub_e") if e.grant == "tier:paid"] == []


def test_a_grant_renamed_and_renamed_back_leaves_one_live_record(ent):
    run(ent, [state("ana", "sub_a")])
    run(ent, [state("ana", "sub_a", grant="status:substack_paid")], run_id="r2")
    plan, _ = run(ent, [state("ana", "sub_a")], run_id="r3")
    assert plan.unseen == [] and [e.grant for e in live_for(ent, "sub_a")] == ["tier:paid"]
    run(ent, [state("ana", "sub_a", status="expired")], run_id="r4")
    assert live_for(ent, "sub_a") == []


def test_a_third_run_after_a_move_changes_nothing_and_sees_everything(ent):
    other = "ed.other@example.org"
    run(ent, [state("ed", "sub_e")])
    run(ent, [state("ed", "sub_e", email=other)], run_id="r2")
    plan, report = run(ent, [state("ed", "sub_e", email=other)], run_id="r3")
    assert (plan.actions, plan.unseen, report.unchanged) == ([], [], 1)


def test_a_member_recognised_by_a_run_gets_the_grant_and_one_tier_event(ent):
    policy = GrantPolicy(
        grant="tier:paid",
        months=6,
        starts="at_claim",
        fixed_until=None,
        requires_live_source=["substack_stripe", "substack_roster"],
        paid_since_before=CUT_OFF,
        plan_intervals=["year"],
    )
    ent.store.put_launch_config(LaunchConfig(join_open=True))
    ent.store.put_campaigns(
        [
            Campaign(
                slug="founding",
                audience="substack_paid",
                opens_at=T0 - timedelta(days=1),
                closes_at=T0 + timedelta(days=60),
                is_default=True,
                grant=policy,
                copy={"headline": "h", "body": "b", "cta": "c"},
                counts={},
            )
        ]
    )
    ent_api.upsert_contact(EMAIL["bo"], ChannelsPatch(platform={"member_uid": "u-bo"}))
    ent.bus.published.clear()
    # An annual reader recorded as a status: only the grant itself makes bo paid.
    _, report = run(ent, [state("bo", "sub_b", grant="status:substack_paid")])
    held = ent.store.entitlements_for_member("u-bo")
    assert sorted(e.source for e in held) == ["grant", "substack_stripe"]
    assert (report.grants_created, report.tier_changes) == (1, 1)
    changed = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert [(e.data["member_uid"], e.data["from"], e.data["to"]) for e in changed] == [
        ("u-bo", "free", "paid")
    ]


# existing_for, and the guard counts renames.


def test_existing_for_returns_every_record_of_the_named_sources_whatever_its_status(ent):
    run(ent, [state("ana", "sub_a"), state("bo", "sub_b"), state("cy", "sub_c")])
    run(
        ent,
        [state("ana", "sub_a"), state("bo", "sub_b", status="expired"), state("cy", "sub_c")],
        run_id="r2",
    )
    [cy] = [
        e for e in ent.store.entitlements_by_source("substack_stripe") if e.source_ref == "sub_c"
    ]
    ent.store.write(cy.contact_id, [cy.model_copy(update={"status": "revoked"})], [])
    ent_api.grant(
        ent_api.contact_id_for(EMAIL["ana"]), "tier:paid", None, "launch", "owner:acc-1", T0
    )
    found = ent_api.existing_for(["substack_stripe", "substack_stripe"])
    assert sorted((e.source_ref, e.status) for e in found) == [
        ("sub_a", "active"),
        ("sub_b", "expired"),
        ("sub_c", "revoked"),
    ]
    assert ent_api.existing_for(["platform_stripe"]) == []


def test_existing_for_feeds_a_second_identical_run_that_changes_nothing(ent):
    states = [
        state("ana", "sub_a"),
        state("hal", "sub_h", grant="status:substack_paid", interval="month"),
    ]
    for run_id in ("r1", "r2"):
        plan = ent_api.plan_reconcile(
            ent_api.existing_for(["substack_stripe"]), states, Guard(), T0
        )
        report = ent_api.apply_plan(plan, run_id, T0)
    assert (plan.actions, plan.unseen, report.unchanged) == ([], [], 2)


NAMES = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]


def renaming(ent, how_many):
    run(ent, [state(n, f"sub_{n}") for n in NAMES])
    for n in NAMES:
        ent_api.claim_for_member(f"u-{n}", ent_api.contact_id_for(EMAIL[n]))
    ent.bus.published.clear()
    states = [state(n, f"sub_{n}", grant="status:substack_paid") for n in NAMES[:how_many]]
    return run(ent, states + [state(n, f"sub_{n}") for n in NAMES[how_many:]], run_id="r2")


def test_the_guard_blocks_a_mass_grant_rename(ent):
    stamped = []
    store_write = ent.store.write

    def spy(contact_id, entitlements, audit):
        stamped.extend(e.updated_by for e in entitlements)
        store_write(contact_id, entitlements, audit)

    ent.store.write = spy
    plan, report = renaming(ent, 6)
    assert plan.blocked and plan.actions == [] and plan.ends == 0
    assert (report.blocked, report.moved, ent.bus.published) == (True, 0, [])
    assert "run:r2" not in stamped
    assert all(
        e.grant == "tier:paid" and e.status == "active"
        for e in ent.store.entitlements_by_source("substack_stripe")
    )


def test_five_grant_renames_of_eight_are_allowed(ent):
    plan, report = renaming(ent, 5)
    assert not plan.blocked and report.moved == 5
