"""Read the subscriber export file the owner downloads from the dashboard.

Columns are found by name. No cell is ever copied into an error or a report,
except a short `Type` value in later tasks (never one that holds an `@`).
"""

import csv
import io
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError

from substack_desk.models import DirectoryListing, SubscriberRecord

REQUIRED_COLUMNS: tuple[str, ...] = ("Email", "Type")


class ExportHeaderError(ValueError):
    def __init__(self, missing: tuple[str, ...]) -> None:
        self.missing = missing
        super().__init__("The export has no column named: " + ", ".join(missing))


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

    records: list[SubscriberRecord] = []
    rejected: dict[str, int] = {}
    unknown_types: dict[str, int] = {}
    rows_read = 0
    free_rows = 0

    for cells in reader:
        if not cells:
            continue
        rows_read += 1
        if len(cells) != len(names):
            _bump(rejected, "wrong_cell_count")
            continue
        kind = cells[type_at].strip().lower()
        if kind == "free":
            free_rows += 1
            continue
        if kind != "paid":
            _bump(rejected, "unknown_type")
            shown = cells[type_at].strip()[:40]
            _bump(unknown_types, "<redacted>" if "@" in shown else shown)
            continue
        try:
            records.append(
                SubscriberRecord(
                    email=cells[email_at],
                    type="paid",
                    plan_interval=None,
                    paid_until=None,
                    since=None,
                )
            )
        except ValidationError:
            _bump(rejected, "bad_email")

    listing = DirectoryListing(
        records=records,
        complete=True,
        rejected_rows=sum(rejected.values()),
        exported_at=exported_at,
    )
    report = ExportReport(
        rows_read=rows_read,
        free_rows=free_rows,
        trial_rows=0,
        rejected=rejected,
        unknown_types=unknown_types,
        unknown_plans={},
        unreadable_dates=0,
    )
    return listing, report
