# substack-desk

## What the Desk is

The Desk is the platform's only way to talk to Substack. It is a standalone Python library: it
imports nothing from `platform_api` and does not depend on it, so it can be extracted and reused.

## What exists today

Only the package skeleton and a test that keeps the boundary. The port of the Substack client and
the capability matrix arrive in the next tasks of the lane.

## How to run the checks

```bash
cd packages/substack-desk
uv run pytest -v && uv run ruff check . && uv run mypy src
```
