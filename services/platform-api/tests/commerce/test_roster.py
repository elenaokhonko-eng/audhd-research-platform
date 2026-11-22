import logging
from datetime import timedelta

from platform_api.commerce import public as commerce
from platform_api.commerce.ports import InMemoryRosterInbox, InMemoryStripeReader, RosterObject
from platform_api.entitlements import public as ent_api
from tests.commerce.test_mapping import sub
from tests.fixtures.people import EMAIL, T0

HEADER = "Email,Type,Stripe plan,First paid date,Expiration date"


def export(*rows):
    return ("\r\n".join([HEADER, *rows]) + "\r\n").encode()


def ready(com, *rows, reconcile_at=T0):
    com.stripe = InMemoryStripeReader([sub("gus"), sub("ana")])
    commerce.stripe_reconcile(False, "schedule", reconcile_at)
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="export.csv", data=export(*rows), updated_at=T0)
    )


DI = f"{EMAIL['di']},Comp,,,"
GUS = f"{EMAIL['gus']},Paid,$5 a year,2026-01-01T00:00:00.000Z,"
ED = f"{EMAIL['ed']},Paid,$5 a year,2026-01-01T00:00:00.000Z,"
BO = f"{EMAIL['bo']},Free,,,"


def test_di_is_recognised_as_a_status_and_gus_gets_nothing_from_the_roster(com, ent):
    ready(com, DI, GUS, BO)
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    roster = ent.store.entitlements_by_source("substack_roster")
    assert [(e.contact_id, e.grant, e.plan_interval) for e in roster] == [
        (ent_api.contact_id_for(EMAIL["di"]), "status:substack_paid", None)
    ]
    assert (
        run.state,
        run.counts["created"],
        run.counts["card_payer_rows"],
        run.counts["card_payer_not_in_stripe"],
    ) == ("completed", 1, 1, 0)
    assert (
        ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])).channels["substack"]["type"]
        == "comp"
    )


def test_a_card_payer_stripe_does_not_show_is_reported_not_granted(com, ent):
    ready(com, ED)
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (
        ent.store.entitlements_by_source("substack_roster") == []
        and run.counts["card_payer_not_in_stripe"] == 1
    )


def test_importing_twice_and_importing_a_shorter_file_end_nothing(com, ent):
    ready(com, DI)
    commerce.roster_import(False, T0 + timedelta(hours=1))
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="e2.csv", data=export(BO), updated_at=T0 + timedelta(hours=2))
    )
    run = commerce.roster_import(False, T0 + timedelta(hours=3))
    assert (run.counts["ended"], run.counts["unseen"]) == (0, 1)
    assert [e.status for e in ent.store.entitlements_by_source("substack_roster")] == ["active"]


def test_a_dry_run_writes_nothing(com, ent):
    ready(com, DI)
    run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert run.counts["created"] == 1 and ent.store.entitlements_by_source("substack_roster") == []
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])) is None


def test_a_cut_off_file_applies_nothing_and_alerts(com, ent, caplog):
    ready(com, DI)
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="cut.csv", data=export(DI)[:-8], updated_at=T0)
    )
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["truncated"]) == (
        "failed",
        1,
    ) and "roster_truncated" in caplog.text
    assert ent.store.entitlements_by_source("substack_roster") == [] and "@" not in caplog.text


def test_the_import_refuses_without_a_recent_good_reconcile(com, ent, caplog):
    com.inbox = InMemoryRosterInbox(RosterObject(name="e.csv", data=export(DI), updated_at=T0))
    with caplog.at_level(logging.ERROR):
        never = commerce.roster_import(False, T0)
    ready(com, DI, reconcile_at=T0)
    stale = commerce.roster_import(False, T0 + timedelta(hours=25))
    assert (never.state, stale.state) == ("failed", "failed") and stale.counts[
        "refused_no_recent_reconcile"
    ] == 1
    assert (
        "roster_refused" in caplog.text
        and ent.store.entitlements_by_source("substack_roster") == []
    )


def test_a_missing_column_fails_and_names_it(com, caplog):
    ready(com, DI)
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="e.csv", data=b"Email,Stripe plan\r\nx@example.org,\r\n", updated_at=T0)
    )
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert run.counts["bad_header"] == 1 and "Type" in caplog.text and "@" not in caplog.text


def test_a_newer_failed_reconcile_refuses_even_after_an_older_good_one(com, ent):
    ready(com, DI, reconcile_at=T0)
    com.stripe = InMemoryStripeReader([sub("gus")], fail_after=0)
    assert commerce.stripe_reconcile(False, "schedule", T0 + timedelta(hours=1)).state == "failed"
    run = commerce.roster_import(False, T0 + timedelta(hours=2))
    assert (run.state, run.counts) == ("failed", {"refused_no_recent_reconcile": 1})
    assert ent.store.entitlements_by_source("substack_roster") == []
