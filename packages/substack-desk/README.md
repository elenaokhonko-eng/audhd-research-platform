# substack-desk

## What the Desk is

The Desk is the platform's only way to talk to Substack. It is a standalone Python library: it
imports nothing from `platform_api` and does not depend on it, so it can be extracted and reused.

## What exists today

- `SubscriberRecord` and `DirectoryListing` (`models.py`): the two shapes the Desk hands to the platform.
- The `SubscriberDirectory` port (`ports.py`): one method, `list_paid()`.
- The capability matrix (`capabilities.py`): `subscriber_directory.file` is on;
  `subscriber_directory.publisher_api` is listed and off; `require()` refuses anything that is off;
  private surfaces are off by default.
- `tests/test_boundary.py` stands in for `lint-imports`: it fails if any source file imports `platform_api`.

- The export-file adapter (`adapters/export_file.py`): `FileDirectory(data, exported_at)` reads the
  owner's export file and satisfies `SubscriberDirectory`. See "Reading the export file".

## Reading the export file

Columns are found by name, in any order. `Email` and `Type` must be there; if not, the Desk stops
and names the missing column. These are used when present: `Stripe plan`, `Expiration date`,
`First paid date`, `Paid upgrade date`, `Group membership`. Every other column is ignored.

A value the Desk does not know is left out and counted, never guessed. The `Type` values it
accepts (any capitals, spaces trimmed):

- `Free` (counted, not listed), `Free trial` (counted, not listed)
- `Paid` and `iOS subscription` (paid; `Paid` with a `Group membership` is a group seat)
- `Comp` and `Complimentary` (comp), `Gift`, `Founding` and `Founding member` (founding), `Lifetime`

A `Stripe plan` cell that contains `year` or `annual` is a yearly plan; one that contains `month`
is monthly. Any other plan text is counted as an unknown plan. The report lists each unknown value
(cut to 40 characters), so compare it with your dashboard before the first dry run.

`complete: false` means the file looks cut off: its last row has fewer or more cells than the
header, or a quoted cell is still open at the end. The rows read before that point are kept for
the dry-run report, and nothing is applied. A short row anywhere else is only rejected and counted.

The report is safe to print. It holds counts, plus any `Type` or
`Stripe plan` value cut to 40 characters (shown as `<redacted>` if it holds an `@`). It never
holds an email address, a name or any other cell.

## How to run the checks

```bash
cd packages/substack-desk
uv run pytest -v && uv run ruff check . && uv run mypy src
```
