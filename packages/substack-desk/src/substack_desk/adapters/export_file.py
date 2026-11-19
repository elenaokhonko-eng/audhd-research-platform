"""Read the subscriber export file the owner downloads from the dashboard.

Columns are found by name. No cell is ever copied into an error or a report,
except a `Type` or `Stripe plan` value cut to 40 characters that the tables
below do not know (never one that holds an `@`; it is shown as `<redacted>`).
`TYPE_VALUES` and `PLAN_WORDS` are the only places a value is interpreted.
"""

import csv
import io
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from substack_desk.capabilities import require
from substack_desk.models import DirectoryListing, SubscriberRecord, SubscriberType

REQUIRED_COLUMNS: tuple[str, ...] = ("Email", "Type")

# Key: the Type cell, trimmed and lower-cased. None means "free": left out of the records.
# "free trial" is handled before this table (the reader has not paid).
TYPE_VALUES: Mapping[str, SubscriberType | None] = {
    "free": None,
    "paid": "paid",
    "ios subscription": "paid",  # billed by Apple; the export is the only source
    "comp": "comp",
    "complimentary": "comp",
    "gift": "gift",
    "founding": "founding",
    "founding member": "founding",
    "lifetime": "lifetime",
}
TRIAL_VALUE = "free trial"

# A lower-cased Stripe plan cell containing the word gets the interval; first match wins.
PLAN_WORDS: tuple[tuple[str, Literal["month", "year"]], ...] = (
    ("year", "year"),
    ("annual", "year"),
    ("month", "month"),
)


class ExportHeaderError(ValueError):
    def __init__(self, missing: tuple[str, ...], message: str | None = None) -> None:
        self.missing = missing
        super().__init__(message or "The export has no column named: " + ", ".join(missing))


class ExportReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows_read: int
    free_rows: int
    trial_rows: int
    rejected: dict[str, int]
    unknown_types: dict[str, int]
    unknown_plans: dict[str, int]
    unreadable_dates: int


def _bump(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _shown(value: str) -> str:
    value = value.strip()
    return "<redacted>" if "@" in value else value[:40]


def _read_date(cell: str) -> tuple[datetime | None, bool]:
    """Return (value, unreadable). An empty cell is (None, False)."""
    text = cell.strip()
    if not text:
        return None, False
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%b %d, %Y")
        except ValueError:
            return None, True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC), False


def _rows(reader: Iterator[list[str]], cut: list[bool]) -> Iterator[tuple[list[str], bool]]:
    """Yield (cells, is_last) for each non-empty row, holding one back to know the last.

    A `csv.Error` (an open quote at the end) is not passed on: its text could hold cell
    content. It sets `cut[0]` and ends the rows; the row held back is then a whole row.
    """
    held: list[str] | None = None
    try:
        for cells in reader:
            if not cells:
                continue
            if held is not None:
                yield held, False
            held = cells
    except csv.Error:
        cut[0] = True
        is_last = False
    else:
        is_last = True
    if held is not None:
        yield held, is_last


def parse_export(text: str, exported_at: datetime) -> tuple[DirectoryListing, ExportReport]:
    text = text.removeprefix("﻿")
    first_line = text.split("\n", 1)[0]
    sep = "\t" if "\t" in first_line else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=sep, strict=True)

    header = next(reader, None)
    names = [h.strip() for h in header] if header else []
    missing = tuple(c for c in REQUIRED_COLUMNS if c not in names)
    if missing:
        raise ExportHeaderError(missing)
    email_at = names.index("Email")
    type_at = names.index("Type")

    def column(cells: list[str], name: str) -> str:
        return cells[names.index(name)].strip() if name in names else ""

    records: list[SubscriberRecord] = []
    rejected: dict[str, int] = {}
    unknown_types: dict[str, int] = {}
    unknown_plans: dict[str, int] = {}
    seen: set[str] = set()
    rows_read = 0
    free_rows = 0
    trial_rows = 0
    unreadable_dates = 0

    cut = [False]
    for cells, is_last in _rows(reader, cut):
        if len(cells) != len(names) and is_last:
            cut[0] = True  # the file ends in the middle of a row
            continue
        rows_read += 1
        if len(cells) != len(names):
            _bump(rejected, "wrong_cell_count")
            continue
        kind = cells[type_at].strip().lower()
        if kind != TRIAL_VALUE and kind not in TYPE_VALUES:
            _bump(rejected, "unknown_type")
            _bump(unknown_types, _shown(cells[type_at]))
            continue
        address = cells[email_at].strip().lower()
        if address in seen:
            _bump(rejected, "duplicate_email")
            continue
        if kind == TRIAL_VALUE:
            trial_rows += 1
            seen.add(address)
            continue
        mapped = TYPE_VALUES[kind]
        if mapped is None:
            free_rows += 1
            seen.add(address)
            continue
        if mapped == "paid" and kind == "paid" and column(cells, "Group membership"):
            mapped = "group_seat"

        plan_cell = column(cells, "Stripe plan")
        plan_text = plan_cell.lower()
        interval = next((value for word, value in PLAN_WORDS if word in plan_text), None)

        paid_until, bad_until = _read_date(column(cells, "Expiration date"))
        since, bad_since = _read_date(column(cells, "First paid date"))
        bad_upgrade = False
        if since is None and not bad_since:
            since, bad_upgrade = _read_date(column(cells, "Paid upgrade date"))
        bad_dates = bad_until + bad_since + bad_upgrade

        try:
            records.append(
                SubscriberRecord(
                    email=cells[email_at],
                    type=mapped,
                    plan_interval=interval,
                    paid_until=paid_until,
                    since=since,
                )
            )
        except ValidationError:
            _bump(rejected, "bad_email")
            continue
        seen.add(address)
        unreadable_dates += bad_dates
        if interval is None and plan_cell:
            _bump(unknown_plans, _shown(plan_cell))

    listing = DirectoryListing(
        records=records,
        complete=not cut[0],
        rejected_rows=sum(rejected.values()),
        exported_at=exported_at,
    )
    report = ExportReport(
        rows_read=rows_read,
        free_rows=free_rows,
        trial_rows=trial_rows,
        rejected=rejected,
        unknown_types=unknown_types,
        unknown_plans=unknown_plans,
        unreadable_dates=unreadable_dates,
    )
    return listing, report


class FileDirectory:
    """A `SubscriberDirectory` that reads the owner's export file."""

    def __init__(self, data: bytes, exported_at: datetime) -> None:
        self._data = data
        self._exported_at = exported_at
        self._report: ExportReport | None = None

    def list_paid(self) -> DirectoryListing:
        require("subscriber_directory.file")
        try:
            text = self._data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise ExportHeaderError((), "The export is not a UTF-8 text file") from None
        listing, self._report = parse_export(text, self._exported_at)
        return listing

    @property
    def report(self) -> ExportReport:
        if self._report is None:
            raise RuntimeError("list_paid has not been called yet")
        return self._report
