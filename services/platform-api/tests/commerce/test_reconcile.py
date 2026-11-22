import logging
from datetime import timedelta

from platform_api.commerce import public as commerce
from platform_api.commerce.ports import InMemoryStripeReader
from tests.commerce.test_mapping import sub
from tests.fixtures.people import T0

PEOPLE = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]


def test_a_real_run_creates_records_and_a_second_changes_nothing(com, ent):
    com.stripe = InMemoryStripeReader(
        [sub("ana"), sub("hal", interval="month"), sub("bo", application="ca_other")]
    )
    first = commerce.stripe_reconcile(False, "schedule", T0)
    second = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (first.state, first.guard, first.counts["created"], first.counts["not_substack"]) == (
        "completed",
        "passed",
        2,
        1,
    )
    assert (second.counts["created"], second.counts["unchanged"]) == (0, 2)
    assert commerce.last_reconcile_completed_at() == T0 + timedelta(minutes=5)
    [event] = [e for e in ent.bus.published if e.type.endswith("commerce.reconcile.completed")][-1:]
    assert event.data["run_id"] == second.run_id and "@" not in event.model_dump_json()


def test_a_dry_run_writes_no_record_but_reports_what_it_would_do(com, ent):
    com.stripe = InMemoryStripeReader([sub("ana")])
    run = commerce.stripe_reconcile(True, "owner", T0)
    assert (run.dry_run, run.counts["created"]) == (True, 1)
    assert ent.store.entitlements_by_source("substack_stripe") == []
    assert commerce.last_reconcile_completed_at() is None  # a dry run is not a completed check


def test_a_read_that_fails_halfway_applies_nothing(com, ent, caplog):
    com.stripe = InMemoryStripeReader([sub(n) for n in PEOPLE])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE], fail_after=3)
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert run.state == "failed" and "reconcile_failed" in caplog.text
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_the_guard_blocks_a_mass_cancellation_and_alerts(com, ent, caplog):
    com.stripe = InMemoryStripeReader([sub(n) for n in PEOPLE])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE])
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (run.state, run.guard, run.counts["ended"]) == ("completed", "blocked", 0)
    assert "reconcile_guard_blocked" in caplog.text
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_a_subscription_missing_from_the_list_is_left_alone(com, ent):
    com.stripe = InMemoryStripeReader([sub("ana"), sub("gus")])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub("ana")])
    run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (run.counts["ended"], run.counts["unseen"]) == (0, 1)


def test_no_address_reaches_the_log_or_the_run_record(com, caplog):
    com.stripe = InMemoryStripeReader([sub("ana"), sub("ed", customer_email=None)])
    with caplog.at_level(logging.DEBUG):
        run = commerce.stripe_reconcile(False, "schedule", T0)
    assert (
        "@" not in caplog.text
        and "@" not in run.model_dump_json()
        and run.counts["no_address"] == 1
    )
