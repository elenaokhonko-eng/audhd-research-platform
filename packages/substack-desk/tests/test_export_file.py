from datetime import UTC, datetime, timedelta

import pytest

from substack_desk.adapters.export_file import ExportHeaderError, FileDirectory, parse_export
from substack_desk.ports import SubscriberDirectory
from tests.export_rows import HEADER, make_export

NOW = datetime(2026, 11, 20, tzinfo=UTC)
ANA = {"Email": "Ana@Example.org ", "Name": "Ana Invented", "Type": "Paid"}
BO = {"Email": "bo@example.org", "Type": "Free"}


def test_paid_rows_are_listed_and_free_rows_are_counted():
    listing, report = parse_export(make_export([ANA, BO]), NOW)
    assert [r.email for r in listing.records] == ["ana@example.org"]
    assert listing.records[0].type == "paid"
    assert (listing.complete, listing.rejected_rows, listing.exported_at) == (True, 0, NOW)
    assert (report.rows_read, report.free_rows) == (2, 1)


@pytest.mark.parametrize("sep", [",", "\t"])
def test_the_separator_is_detected(sep):
    listing, _ = parse_export(make_export([ANA], sep=sep), NOW)
    assert len(listing.records) == 1


def test_columns_are_found_by_name_in_any_order_and_a_bom_is_ignored():
    text = "﻿" + make_export([ANA], header=list(reversed(HEADER)))
    assert len(parse_export(text, NOW)[0].records) == 1


def test_a_missing_required_column_is_named():
    header = [h for h in HEADER if h != "Type"]
    with pytest.raises(ExportHeaderError) as err:
        parse_export(make_export([{"Email": "ana@example.org"}], header=header), NOW)
    assert err.value.missing == ("Type",)
    assert "Type" in str(err.value) and "@" not in str(err.value)


def test_an_empty_file_has_no_header():
    with pytest.raises(ExportHeaderError):
        parse_export("", NOW)


def test_a_bad_address_is_rejected_without_being_repeated():
    listing, report = parse_export(make_export([{"Email": "not-an-address", "Type": "Paid"}, ANA]), NOW)
    assert listing.rejected_rows == 1 and report.rejected == {"bad_email": 1}
    assert "not-an-address" not in report.model_dump_json()


def paid(**over):
    return {"Email": "ana@example.org", "Type": "Paid", **over}


@pytest.mark.parametrize(
    ("cell", "group", "expected"),
    [("paid", "", "paid"), ("Paid", "Team A", "group_seat"), ("Comp", "", "comp"), ("complimentary", "", "comp"),
     ("Gift", "", "gift"), ("Founding", "", "founding"), ("Lifetime", "", "lifetime"), ("iOS Subscription", "", "paid")],
)
def test_types(cell, group, expected):
    listing, _ = parse_export(make_export([paid(Type=cell, **{"Group membership": group})]), NOW)
    assert listing.records[0].type == expected


def test_a_free_trial_is_not_a_paying_reader():
    listing, report = parse_export(make_export([paid(Type="Free Trial")]), NOW)
    assert listing.records == [] and listing.rejected_rows == 0
    assert (report.trial_rows, report.free_rows) == (1, 0)


def test_an_unknown_type_is_rejected_and_reported_never_guessed():
    listing, report = parse_export(make_export([paid(Type="Patron"), paid(Type="")]), NOW)
    assert listing.records == [] and report.free_rows == 0
    assert report.rejected == {"unknown_type": 2}
    assert report.unknown_types == {"Patron": 1, "": 1}


def test_a_reported_value_never_carries_an_address():
    _, report = parse_export(make_export([paid(Type="x@example.org"), paid(Type="y" * 60)]), NOW)
    assert set(report.unknown_types) == {"<redacted>", "y" * 40}


@pytest.mark.parametrize(
    ("cell", "expected", "unknown"),
    [("Annual", "year", {}), ("yearly", "year", {}), ("Monthly", "month", {}), ("", None, {}), ("Weekly", None, {"Weekly": 1}),
     ("$5 a month", "month", {}), ("CA$70 a year", "year", {})],
)
def test_plans(cell, expected, unknown):
    listing, report = parse_export(make_export([paid(**{"Stripe plan": cell})]), NOW)
    assert listing.records[0].plan_interval == expected and report.unknown_plans == unknown


def test_an_unknown_plan_with_an_address_is_redacted():
    _, report = parse_export(make_export([paid(**{"Stripe plan": "x@example.org"})]), NOW)
    assert report.unknown_plans == {"<redacted>": 1}


def test_dates():
    row = paid(**{"Expiration date": "2027-03-01T00:00:00Z", "First paid date": "", "Paid upgrade date": "2026-03-01",
                  "Start date": "2025-01-01"})
    record = parse_export(make_export([row]), NOW)[0].records[0]
    assert record.paid_until == datetime(2027, 3, 1, tzinfo=UTC)
    assert record.since == datetime(2026, 3, 1, tzinfo=UTC)          # not the Start date


def test_a_millisecond_utc_timestamp_is_read():
    record = parse_export(make_export([paid(**{"First paid date": "2026-04-14T11:36:24.329Z"})]), NOW)[0].records[0]
    assert record.since == datetime(2026, 4, 14, 11, 36, 24, 329000, tzinfo=UTC)


def test_the_dashboard_form_of_a_date_is_read_too():
    record = parse_export(make_export([paid(**{"First paid date": "Nov 17, 2026"})]), NOW)[0].records[0]
    assert record.since == datetime(2026, 11, 17, tzinfo=UTC)


def test_an_unreadable_date_is_counted_and_the_row_kept():
    listing, report = parse_export(make_export([paid(**{"Expiration date": "next spring"})]), NOW)
    assert listing.records[0].paid_until is None and report.unreadable_dates == 1


def test_the_first_of_two_rows_with_one_address_wins():
    rows = [paid(**{"Stripe plan": "Annual"}), paid(Email=" ANA@example.org", **{"Stripe plan": "Monthly"})]
    listing, report = parse_export(make_export(rows), NOW)
    assert [r.plan_interval for r in listing.records] == ["year"]
    assert report.rejected == {"duplicate_email": 1}


def test_an_address_after_the_cut_is_still_redacted():
    long_value = "a" * 45 + "@example.org"
    _, report = parse_export(make_export([paid(Type=long_value), paid(**{"Stripe plan": long_value})]), NOW)
    assert report.unknown_types == {"<redacted>": 1}
    assert report.unknown_plans == {"<redacted>": 1}


def test_a_rejected_row_adds_nothing_to_plan_or_date_counts():
    row = paid(Email="not-an-address", **{"Stripe plan": "Weekly", "Expiration date": "next spring"})
    listing, report = parse_export(make_export([row]), NOW)
    assert listing.records == [] and report.rejected == {"bad_email": 1}
    assert report.unknown_plans == {} and report.unreadable_dates == 0


def test_a_date_with_an_offset_is_normalised_to_utc():
    record = parse_export(make_export([paid(**{"First paid date": "2026-04-14T16:36:24+05:00"})]), NOW)[0].records[0]
    assert record.since.utcoffset() == timedelta(0)
    assert record.since == datetime(2026, 4, 14, 11, 36, 24, tzinfo=UTC)


CY = {"Email": "cy@example.org", "Type": "Paid"}


def test_a_last_row_cut_short_makes_the_listing_incomplete():
    text = make_export([ANA, CY])
    cut = text[: text.rindex("cy@example.org") + len("cy@example.org,Pa")]
    listing, report = parse_export(cut, NOW)
    assert listing.complete is False
    assert [r.email for r in listing.records] == ["ana@example.org"] and listing.rejected_rows == 0


def test_a_short_row_in_the_middle_is_only_rejected():
    lines = make_export([ANA, CY]).split("\r\n")
    lines.insert(2, "di@example.org,Paid")
    listing, report = parse_export("\r\n".join(lines), NOW)
    assert listing.complete is True and report.rejected == {"wrong_cell_count": 1}
    assert len(listing.records) == 2


def test_an_open_quote_at_the_end_makes_the_listing_incomplete():
    listing, _ = parse_export(make_export([ANA]) + '"cy@example.org,Paid', NOW)
    assert listing.complete is False and len(listing.records) == 1


def test_file_directory_is_a_subscriber_directory_with_a_report():
    directory: SubscriberDirectory = FileDirectory(make_export([ANA, BO]).encode(), NOW)
    with pytest.raises(RuntimeError):
        directory.report  # type: ignore[attr-defined]  # noqa: B018
    assert len(directory.list_paid().records) == 1
    assert directory.report.free_rows == 1  # type: ignore[attr-defined]


def test_bytes_that_are_not_text_are_refused():
    with pytest.raises(ExportHeaderError, match="UTF-8"):
        FileDirectory(b"\xff\xfe\x00", NOW).list_paid()
