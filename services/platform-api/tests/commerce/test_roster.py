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


def test_a_reader_stripe_already_holds_gets_no_roster_record(com, ent):
    ready(com, f"{EMAIL['gus']},Comp,,,")
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert ent.store.entitlements_by_source("substack_roster") == []
    assert (run.state, run.counts["already_in_stripe"], run.counts["created"]) == (
        "completed",
        1,
        0,
    )
    channels = ent.store.get_contact(ent_api.contact_id_for(EMAIL["gus"])).channels
    assert channels["substack"]["type"] == "comp"


def test_an_unknown_plan_refuses_and_writes_nothing(com, ent, caplog):
    ready(com, DI, f"{EMAIL['ed']},Paid,Founding member,,")
    with caplog.at_level(logging.WARNING):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["unknown_plans"]) == ("failed", 1)
    assert "roster_refused" in caplog.text and "reason=unknown_plans" in caplog.text
    assert "@" not in caplog.text
    assert ent.store.entitlements_by_source("substack_roster") == []
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])) is None
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["ed"])) is None


def test_unreadable_dates_are_counted_and_logged(com, caplog):
    ready(com, f"{EMAIL['di']},Comp,,not a date,")
    with caplog.at_level(logging.WARNING):
        run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert run.counts["unreadable_dates"] == 1
    assert "roster_unreadable_dates" in caplog.text and "dry_run=True" in caplog.text


def test_a_file_that_is_not_utf8_fails_and_says_so(com, caplog):
    ready(com, DI)
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="e.csv", data=b"\xff\xfe\x00bad", updated_at=T0)
    )
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["bad_header"]) == ("failed", 1)
    assert "reason=not_utf8" in caplog.text and "@" not in caplog.text


def test_reuploading_the_same_dateless_file_changes_nothing(com, ent):
    ready(com, DI)
    commerce.roster_import(False, T0 + timedelta(hours=1))
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="e2.csv", data=export(DI), updated_at=T0 + timedelta(hours=2))
    )
    run = commerce.roster_import(False, T0 + timedelta(hours=3))
    assert (run.state, run.counts["updated"], run.counts["unchanged"]) == ("completed", 0, 1)


def test_a_card_payer_contact_records_what_the_roster_says(com, ent):
    ready(com, GUS)
    now = T0 + timedelta(hours=1)
    run = commerce.roster_import(False, now)
    substack = ent.store.get_contact(ent_api.contact_id_for(EMAIL["gus"])).channels["substack"]
    assert (substack["plan_interval"], substack["last_seen_in_roster"]) == ("year", now.isoformat())
    assert run.counts["writing_contacts"] == 1


def test_an_empty_inbox_fails(com, caplog):
    ready(com, DI)
    com.inbox = InMemoryRosterInbox()
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts) == ("failed", {"no_file": 1})
    assert "roster_no_file" in caplog.text


def test_an_unexpected_error_fails_the_run_and_logs_only_its_class(com, ent, monkeypatch, caplog):
    ready(com, DI)

    def broken(*args, **kwargs):
        raise ValueError(f"cannot plan for {EMAIL['di']}")

    monkeypatch.setattr(ent_api, "plan_reconcile", broken)
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert run.state == "failed" and "error=ValueError" in caplog.text
    assert "@" not in caplog.text and "cannot plan" not in caplog.text
    assert ent.store.entitlements_by_source("substack_roster") == []


def test_rows_free_rows_and_trial_rows_are_counted(com):
    ready(com, DI, BO, f"{EMAIL['cy']},Free trial,,,")
    run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert (run.counts["rows"], run.counts["free_rows"], run.counts["trial_rows"]) == (3, 1, 1)


def test_a_file_without_the_stripe_plan_column_fails_and_names_it(com, ent, caplog):
    ready(com, DI)
    data = f"Email,Type,First paid date,Expiration date\r\n{EMAIL['di']},Comp,,\r\n".encode()
    com.inbox = InMemoryRosterInbox(RosterObject(name="e.csv", data=data, updated_at=T0))
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["bad_header"]) == ("failed", 1)
    assert "Stripe plan" in caplog.text and "@" not in caplog.text
    assert ent.store.entitlements_by_source("substack_roster") == []
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])) is None


def test_a_comp_reader_who_moved_to_card_is_counted_and_keeps_the_record(com, ent):
    ready(com, DI)
    commerce.roster_import(False, T0 + timedelta(hours=1))
    commerce.stripe_reconcile(False, "schedule", T0 + timedelta(hours=2))
    di_paid = f"{EMAIL['di']},Paid,$5 a year,2026-01-01T00:00:00.000Z,"
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="e2.csv", data=export(di_paid), updated_at=T0 + timedelta(hours=2))
    )
    run = commerce.roster_import(False, T0 + timedelta(hours=3))
    assert (run.state, run.counts["roster_record_now_card_payer"]) == ("completed", 1)
    assert [e.status for e in ent.store.entitlements_by_source("substack_roster")] == ["active"]


def test_a_row_whose_paid_period_ended_creates_no_record(com, ent):
    ready(com, f"{EMAIL['di']},Comp,,,2026-01-01T00:00:00.000Z")
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["expired_rows"], run.counts["expired_rows_with_record"]) == (
        "completed",
        1,
        0,
    )
    assert ent.store.entitlements_by_source("substack_roster") == []


def test_a_row_whose_paid_period_ended_leaves_an_existing_record_alone(com, ent):
    ready(com, DI)
    commerce.roster_import(False, T0 + timedelta(hours=1))
    ended = f"{EMAIL['di']},Comp,,,2026-01-01T00:00:00.000Z"
    com.inbox = InMemoryRosterInbox(
        RosterObject(name="e2.csv", data=export(ended), updated_at=T0 + timedelta(hours=2))
    )
    run = commerce.roster_import(False, T0 + timedelta(hours=3))
    assert (run.counts["expired_rows_with_record"], run.counts["unseen"], run.counts["ended"]) == (
        1,
        1,
        0,
    )
    assert [e.status for e in ent.store.entitlements_by_source("substack_roster")] == ["active"]


def test_rejected_rows_are_counted_by_reason(com):
    ready(com, DI, f"{EMAIL['di']},Paid,$5 a year,,")
    run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert (run.counts["rejected_rows"], run.counts["rejected_duplicate_email"]) == (1, 1)


def test_paid_rows_without_a_plan_and_the_export_time_are_counted(com):
    ready(com, f"{EMAIL['di']},Paid,,,")
    run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert (run.counts["paid_rows_without_plan"], run.counts["created"]) == (1, 1)
    assert run.counts["export_updated_at"] == int(T0.timestamp())


def test_unknown_plans_count_rows(com):
    ed = f"{EMAIL['ed']},Paid,Founding member,,"
    ready(com, ed, f"{EMAIL['cy']},Paid,Founding member,,")
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["unknown_plans"]) == ("failed", 2)


def test_a_dry_run_with_an_unknown_plan_is_refused(com, ent, caplog):
    ready(com, DI, f"{EMAIL['ed']},Paid,Founding member,,")
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert run.state == "failed" and "alert=roster_refused" in caplog.text
    assert "dry_run=True" in caplog.text and "@" not in caplog.text
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])) is None


def test_an_address_in_other_case_is_still_the_reader_stripe_holds(com, ent):
    ready(com, f"{EMAIL['gus'].upper()},Comp,,,")
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert run.counts["already_in_stripe"] == 1
    assert ent.store.entitlements_by_source("substack_roster") == []
