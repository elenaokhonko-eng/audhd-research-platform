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
    first = commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE], fail_after=3)
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert run.state == "failed" and "reconcile_failed" in caplog.text
    assert run.counts["seen"] == 3
    assert [
        e.data["run_id"]
        for e in ent.bus.published
        if e.type.endswith("commerce.reconcile.completed")
    ] == [first.run_id]
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_the_guard_blocks_a_mass_cancellation_and_alerts(com, ent, caplog):
    com.stripe = InMemoryStripeReader([sub(n) for n in PEOPLE])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE])
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (run.state, run.guard, run.counts["ended"]) == ("completed", "blocked", 0)
    assert (run.counts["guard_ends"], run.counts["live_before"]) == (8, 8)
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


def test_a_failing_event_publish_leaves_the_run_completed(com, caplog):
    class BrokenBus:
        def publish(self, event):
            raise RuntimeError("bus down")

    com.bus = BrokenBus()
    com.stripe = InMemoryStripeReader([sub("ana")])
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0)
    assert (run.state, run.counts["created"]) == ("completed", 1)
    assert "reconcile_failed" not in caplog.text and "reconcile_event_not_published" in caplog.text


def test_a_failure_outside_the_read_keeps_its_counts_and_applies_nothing(
    com, ent, caplog, monkeypatch
):
    from platform_api.commerce import reconcile
    from platform_api.commerce.mapping import to_state

    calls = []

    def flaky(s, settings, now):
        calls.append(s.id)
        if len(calls) == 2:
            raise RuntimeError("boom ana@example.org")
        return to_state(s, settings, now)

    monkeypatch.setattr(reconcile, "to_state", flaky)
    com.stripe = InMemoryStripeReader([sub("ana"), sub("cy")])
    with caplog.at_level(logging.DEBUG):
        run = commerce.stripe_reconcile(False, "schedule", T0)
    assert run.state == "failed" and run.counts["seen"] == 2
    assert "RuntimeError" in caplog.text and "@" not in caplog.text
    assert "dry_run=False" in caplog.text
    assert ent.store.entitlements_by_source("substack_stripe") == []


def test_alert_lines_say_whether_it_was_a_dry_run(com, caplog):
    com.stripe = InMemoryStripeReader([sub(n) for n in PEOPLE])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE])
    with caplog.at_level(logging.ERROR):
        commerce.stripe_reconcile(True, "owner", T0 + timedelta(minutes=5))
    assert any(
        m.startswith("alert=reconcile_guard_blocked") and "dry_run=True" in m
        for m in caplog.messages
    )


def test_no_reader_fails_the_run(com, caplog):
    com.stripe = None
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0)
    assert (run.state, run.counts["no_reader"]) == ("failed", 1)
    assert "reconcile_failed" in caplog.text


def test_the_fake_run_store_breaks_ties_toward_the_latest_insert():
    from platform_api.commerce.ports import InMemoryRunStore

    store = InMemoryRunStore()
    a = store.start("stripe_reconcile", False, "schedule", T0)
    b = store.start("stripe_reconcile", False, "schedule", T0)
    store.finish(a, "completed", "passed", {}, T0)
    store.finish(b, "completed", "passed", {}, T0)
    assert store.latest("stripe_reconcile").run_id == b


def test_a_failure_while_applying_is_marked_part_applied(com, monkeypatch):
    from platform_api.entitlements import public as entitlements

    def boom(plan, run_id, now):
        raise RuntimeError("write failed")

    monkeypatch.setattr(entitlements, "apply_plan", boom)
    com.stripe = InMemoryStripeReader([sub("ana")])
    run = commerce.stripe_reconcile(False, "schedule", T0)
    assert run.state == "failed" and run.counts["applying"] == 1


def test_every_state_is_counted_by_status_and_adds_up_to_seen(com):
    com.stripe = InMemoryStripeReader(
        [sub("ana"), sub("cy", status="canceled"), sub("ed", customer_email=None)]
    )
    run = commerce.stripe_reconcile(False, "schedule", T0)
    c = run.counts
    skips = ("not_substack", "no_address", "bad_address", "incomplete", "past_due_unknown")
    assert (c["states_active"], c["states_expired"], c["states_grace"]) == (1, 1, 0)
    assert c["seen"] == c["states_active"] + c["states_grace"] + c["states_expired"] + sum(
        c[k] for k in skips
    )


def test_an_active_subscription_without_a_period_end_is_counted(com):
    com.stripe = InMemoryStripeReader([sub("ana", current_period_end=None), sub("cy")])
    run = commerce.stripe_reconcile(False, "schedule", T0)
    assert (run.counts["no_period_end"], run.counts["states_active"]) == (1, 2)
