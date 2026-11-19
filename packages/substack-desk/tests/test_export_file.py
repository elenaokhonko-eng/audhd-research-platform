from datetime import UTC, datetime

import pytest

from substack_desk.adapters.export_file import ExportHeaderError, parse_export
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
