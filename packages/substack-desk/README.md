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

The export-file adapter, `FileDirectory`, comes next.

## How to run the checks

```bash
cd packages/substack-desk
uv run pytest -v && uv run ruff check . && uv run mypy src
```
