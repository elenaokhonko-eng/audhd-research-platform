# Lane L6 Desk · Export File Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `substack_desk` can read the subscriber export file that Substack's dashboard produces and answer "who are the paying subscribers" as a `DirectoryListing`, without guessing: a row it does not understand is counted and left out, and a file that is cut off is reported as incomplete.

**Architecture:** One pure function turns the text of an export into a listing and a report; one small class wraps it as the `SubscriberDirectory` port. An **adapter** is one way of answering a port; this is the first. It reads a file the owner uploaded. It makes no network call and knows nothing about the platform. The platform's `roster-import` job (task card M5) is the only caller.

**Tech Stack:** Python 3.12 standard library (`csv`, `datetime`), Pydantic v2, pytest.

**Spec:** [contracts](../../contracts/stage-1-launch.md) §3 (`SubscriberRecord`, `DirectoryListing`, `SubscriberDirectory`) · task card D2 in the [swarm build plan](../../plans/stage-1-swarm-build-plan.md) · `docs/architecture/05-substack-desk.md` · the [package skeleton plan](2026-11-20-lane-desk-package-skeleton.md), which must be merged first.

**Lane rules:** change only `packages/substack-desk/`. Branch `desk/export-file-adapter` from `integration/stage-1`; one draft pull request against it.

## Global Constraints

- No row of a real export enters the repository, a test, a log line or an error message. Test rows are invented people at `example.org`.
- An error message or a report may contain: a column name, a count, a row **number**, and a value of the `Type` or `Stripe plan` column cut to 40 characters. It never contains an email address, a name, or any other cell. A reported value that contains `@` is replaced by `<redacted>`.
- The header of the export, as supplied by the owner on 2026-11-20 (column names only). The adapter reads columns **by name**, in any order, and ignores columns it does not use:

```text
Email, Name, Type, Activity, Start date, Revenue, Comments, Comments (7d), Comments (30d), Shares, Shares (7d),
Shares (30d), Country, State/Province, Time zone, Emails received (6mo), Emails dropped (6mo), num_emails_opened,
Emails opened (6mo), Emails opened (7d), Emails opened (30d), Last email open, Links clicked, Last clicked at,
Video plays (30d), Unique videos played (30d), Last video played, Podcast plays (30d), Unique podcasts played (30d),
Last podcast played, Unique emails seen (6mo), Unique emails seen (7d), Unique emails seen (30d), Post views,
Post views (7d), Post views (30d), Unique posts seen, Unique posts seen (7d), Unique posts seen (30d),
Subscriptions gifted, Expiration date, Subscription source (free), Subscription source (paid), Days active (30d),
First paid date, Paid upgrade date, Cancel date, Cancel reason, Cancel feedback, Bestseller, Stripe plan, Sections,
Group membership
```

- Columns the adapter uses: `Email` and `Type` (required); `Stripe plan`, `Expiration date`, `First paid date`, `Paid upgrade date`, `Group membership` (optional: when one is absent its value is treated as empty). `Name` and every other column are never read into memory beyond the row being parsed and are never stored.
- The separator is detected from the header line: a tab if the line contains a tab, otherwise a comma. (The owner's copy of the header arrived tab-separated; the file itself may use commas.)
- **Values are provisional.** The owner has supplied the column names but not the values these columns take. The mappings below are written from the dashboard's labels. Unknown values are never guessed: the row is left out and the value is counted in the report, so the first dry run on the real file shows what is missing. The integrator updates the two mapping tables when the owner sends the distinct values of `Type` and `Stripe plan`.
- Check command for every task: `cd packages/substack-desk && uv run pytest -v && uv run ruff check . && uv run mypy src`.

## Review Focus

1. **A file cut off in the middle.** A last row with fewer cells than the header, or a quoted cell that never closes, gives `complete: false`. The platform then applies nothing. Pinned in Task 3.
2. **A value of `Type` nobody has seen.** The row is rejected and counted; it is never treated as paid and never as free. Pinned in Task 2.
3. **A required column renamed by Substack.** `ExportHeaderError` names the missing column; no listing is returned. Pinned in Task 1.
4. **An email address leaking into an error or the report.** Pinned in Tasks 1 and 2 by tests that search every message for `@`.
5. **The same address twice.** The first row wins, the later one is rejected. Pinned in Task 2.

---

## File Structure

```
packages/substack-desk/
├─ src/substack_desk/adapters/__init__.py
├─ src/substack_desk/adapters/export_file.py   parse_export, ExportReport, ExportHeaderError, FileDirectory
└─ tests/
   ├─ export_rows.py                            HEADER and make_export(), shared by the tests
   └─ test_export_file.py
```

---

### Task 1: The header and the plain rows

**Files:**
- Create: `src/substack_desk/adapters/__init__.py`, `src/substack_desk/adapters/export_file.py`, `tests/export_rows.py`, `tests/test_export_file.py`

**Interfaces:**
- Consumes: `SubscriberRecord`, `DirectoryListing` from `substack_desk.models`.
- Produces:

```python
REQUIRED_COLUMNS: tuple[str, ...] = ("Email", "Type")

class ExportHeaderError(ValueError):
    missing: tuple[str, ...]            # message: "The export has no column named: Email, Type"

class ExportReport(BaseModel):          # frozen
    rows_read: int
    free_rows: int
    rejected: dict[str, int]            # reason -> count; reasons: "bad_email", "duplicate_email",
                                        # "unknown_type", "wrong_cell_count"
    unknown_types: dict[str, int]       # value (cut to 40 characters) -> count
    unknown_plans: dict[str, int]
    unreadable_dates: int

def parse_export(text: str, exported_at: datetime) -> tuple[DirectoryListing, ExportReport]: ...
```

- `tests/export_rows.py`: `HEADER: list[str]` (the 53 names above, in that order) and `make_export(rows: list[dict[str, str]], sep: str = ",", header: list[str] | None = None) -> str`, which writes the header and one line per row with `csv.writer`, an empty cell for every column a row does not name, and `\r\n` line ends.
- A leading byte-order mark is ignored. Header names are compared after trimming spaces, exactly otherwise (case matters).
- In this task every `Type` other than `Free` and `Paid` (compared without regard to case) is rejected as `unknown_type`; Task 2 widens the mapping. `Free` rows are counted in `free_rows` and left out. `plan_interval`, `paid_until` and `since` are `None` in this task.
- `rejected_rows` of the listing is the sum of `rejected`'s counts. `complete` is `True` in this task.

- [ ] **Step 1: Write the failing tests**

```python
# packages/substack-desk/tests/test_export_file.py
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
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/test_export_file.py -v`
Expected: FAIL, `No module named 'substack_desk.adapters'`.

- [ ] **Step 3: Implement `parse_export`, `ExportReport`, `ExportHeaderError`**

Read with `csv.reader(io.StringIO(text, newline=""), delimiter=sep, strict=True)`. Build each `SubscriberRecord` inside `try/except ValidationError`; a failure on the address is `bad_email`.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 7 new tests pass (the parametrised one counts twice); no lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/substack-desk
git commit -m "desk: read the subscriber export by column name"
```

---

### Task 2: Types, plans, dates and duplicates

**Files:**
- Modify: `src/substack_desk/adapters/export_file.py`, `tests/test_export_file.py`

**Interfaces:**
- Produces two module constants, the only places a value of the export is interpreted:

```python
TYPE_VALUES: Mapping[str, SubscriberType | None]   # key: the cell, trimmed and lower-cased; None means "free"
PLAN_WORDS: tuple[tuple[str, Literal["month", "year"]], ...]
```

| `Type` cell (any case) | Becomes |
| --- | --- |
| `free` | left out, counted in `free_rows` |
| `paid` | `paid`; or `group_seat` when `Group membership` is not empty |
| `comp`, `complimentary` | `comp` |
| `gift` | `gift` |
| `founding`, `founding member` | `founding` |
| `lifetime` | `lifetime` |
| anything else, including empty | rejected as `unknown_type`; the value is counted in `unknown_types` |

| `Stripe plan` cell (any case) | `plan_interval` |
| --- | --- |
| contains `year` or `annual` | `year` |
| contains `month` | `month` |
| empty | `None` |
| anything else | `None`; the value is counted in `unknown_plans` (the row is kept) |

- `paid_until` is the `Expiration date` cell. `since` is the `First paid date` cell and, when that is empty, the `Paid upgrade date` cell; `Start date` is **not** used, because it is the day the reader first subscribed for free.
- A date cell is read with `datetime.fromisoformat` after replacing a final `Z` with `+00:00`. A value without a time zone, or a date without a time, is taken as UTC. An empty cell is `None`. A cell that cannot be read is `None` and adds one to `unreadable_dates`; the row is kept.
- The second and later rows with an address already seen (after trimming and lower-casing) are rejected as `duplicate_email`. An address counts as seen only when its row was kept as a record or counted as a free row; the type is checked before the duplicate.

- [ ] **Step 1: Write the failing tests**

```python
def paid(**over):
    return {"Email": "ana@example.org", "Type": "Paid", **over}


@pytest.mark.parametrize(
    ("cell", "group", "expected"),
    [("paid", "", "paid"), ("Paid", "Team A", "group_seat"), ("Comp", "", "comp"), ("complimentary", "", "comp"),
     ("Gift", "", "gift"), ("Founding", "", "founding"), ("Lifetime", "", "lifetime")],
)
def test_types(cell, group, expected):
    listing, _ = parse_export(make_export([paid(Type=cell, **{"Group membership": group})]), NOW)
    assert listing.records[0].type == expected


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
    [("Annual", "year", {}), ("yearly", "year", {}), ("Monthly", "month", {}), ("", None, {}), ("Weekly", None, {"Weekly": 1})],
)
def test_plans(cell, expected, unknown):
    listing, report = parse_export(make_export([paid(**{"Stripe plan": cell})]), NOW)
    assert listing.records[0].plan_interval == expected and report.unknown_plans == unknown


def test_dates():
    row = paid(**{"Expiration date": "2027-03-01T00:00:00Z", "First paid date": "", "Paid upgrade date": "2026-03-01",
                  "Start date": "2025-01-01"})
    record = parse_export(make_export([row]), NOW)[0].records[0]
    assert record.paid_until == datetime(2027, 3, 1, tzinfo=UTC)
    assert record.since == datetime(2026, 3, 1, tzinfo=UTC)          # not the Start date


def test_an_unreadable_date_is_counted_and_the_row_kept():
    listing, report = parse_export(make_export([paid(**{"Expiration date": "next spring"})]), NOW)
    assert listing.records[0].paid_until is None and report.unreadable_dates == 1


def test_the_first_of_two_rows_with_one_address_wins():
    rows = [paid(**{"Stripe plan": "Annual"}), paid(Email=" ANA@example.org", **{"Stripe plan": "Monthly"})]
    listing, report = parse_export(make_export(rows), NOW)
    assert [r.plan_interval for r in listing.records] == ["year"]
    assert report.rejected == {"duplicate_email": 1}
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/test_export_file.py -v`
Expected: FAIL on the new tests (types other than `Paid` are rejected; intervals and dates are `None`).

- [ ] **Step 3: Implement the two tables, the date reader and the duplicate check**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 17 new tests pass (7 types, 5 plans, 5 others); no lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/substack-desk
git commit -m "desk: interpret type, plan and dates of the export; reject what is unknown"
```

---

### Task 3: A file that is cut off, and the port

**Files:**
- Modify: `src/substack_desk/adapters/export_file.py`, `tests/test_export_file.py`, `README.md`

**Interfaces:**
- Produces:

```python
class FileDirectory:                                 # satisfies SubscriberDirectory
    def __init__(self, data: bytes, exported_at: datetime) -> None: ...
    def list_paid(self) -> DirectoryListing: ...     # calls require("subscriber_directory.file") first
    @property
    def report(self) -> ExportReport: ...            # of the last list_paid; raises RuntimeError before the first
```

- `data` is decoded as UTF-8 with `errors="strict"`; bytes that are not UTF-8 raise `ExportHeaderError` with the message "The export is not a UTF-8 text file" and `missing == ()`.
- A row whose number of cells differs from the header's: if it is the **last** row of the file, the listing is `complete: false` and the row is not counted as rejected; anywhere else it is rejected as `wrong_cell_count`.
- A quoted cell that is still open at the end of the file (`csv.Error` from the strict reader): `complete: false`, with the rows read before it.
- `complete: false` keeps the records read so far, for the dry-run report. The contracts page says what the caller does with it: nothing is applied.

- [ ] **Step 1: Write the failing tests**

```python
from substack_desk.adapters.export_file import FileDirectory
from substack_desk.ports import SubscriberDirectory

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
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/test_export_file.py -v`
Expected: FAIL, `cannot import name 'FileDirectory'`.

- [ ] **Step 3: Implement, and add a "Reading the export file" section to `README.md`**

The section says, in this order: which columns are used; that unknown values are left out and counted; what `complete: false` means; and that the report is safe to print because it holds counts and column values only.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 5 new tests pass, 29 in this file; `tests/test_boundary.py` still passes.

- [ ] **Step 5: Commit**

```bash
git add packages/substack-desk
git commit -m "desk: FileDirectory adapter; a cut-off export is reported as incomplete"
```

---

## Exit test for this plan

1. The check command passes in `packages/substack-desk`, locally and in CI.
2. A search of the lane's diff finds no address outside `example.org` and no row copied from a real export.
3. The hand-over summary lists the values of `Type` and `Stripe plan` the two tables accept, so the owner can compare them with her dashboard before the first dry run.
