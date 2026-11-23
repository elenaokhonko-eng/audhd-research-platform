"""The commerce jobs, run as `platform-cli job <name>` (contracts section 6).

Each job builds the commerce runtime from the cloud adapters, reads
`PLATFORM_JOB_DRY_RUN` (`1` is a dry run; unset, empty or `0` a real one; anything else
stops the job) and `PLATFORM_JOB_REQUESTED_BY` (default `schedule`), runs once at
`clock.utcnow()`, and prints the run as one JSON line: counts only, never an address.

Exit codes: 0 completed with the guard passed; 1 failed; 2 completed with the guard
blocked. Any other ending exits 1 and prints one line naming the exception's class only:
- a job that cannot set up (a setting refused, the secret unreadable, a client that cannot
  be built) prints `{"job", "error"}`; it stops before a run is started;
- an exception that escapes the run after it started (`stripe_reconcile` and
  `roster_import` catch their own; this is a run record that could not be written or read)
  prints `{"job", "run_id", "error"}` and, unless the run is known to have finished, tries
  once more to finish it as `failed` with the counts it was last given, so it is not left
  `running`.

Only `stripe-reconcile` reads the Stripe key, from the Secret Manager name in
`PLATFORM_STRIPE_KEY_SECRET`. Importing this module creates no cloud client; a job uses the
bus and the Firestore client `platform-cli job` made (`use_clients`), never its own.
"""

import json
import os
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import TypeAdapter

from platform_api.commerce.models import RequestedBy, RunKind, SyncRun
from platform_api.settings import Settings

if TYPE_CHECKING:
    from platform_api.commerce.ports import RunStore
    from platform_api.shared.bus import EventBus

_DRY_RUN = {"": False, "0": False, "1": True}


class SettingRefused(Exception):
    """A setting the job needs is missing or not one it accepts."""


def exit_code(run: SyncRun) -> int:
    if run.state == "completed" and run.guard == "passed":
        return 0
    if run.state == "completed" and run.guard == "blocked":
        return 2
    return 1


def _job_environment() -> tuple[bool, RequestedBy]:
    flag = os.environ.get("PLATFORM_JOB_DRY_RUN", "").strip()
    if flag not in _DRY_RUN:
        raise SettingRefused
    requested_by: RequestedBy = TypeAdapter(RequestedBy).validate_python(
        os.environ.get("PLATFORM_JOB_REQUESTED_BY", "schedule").strip()
    )
    return _DRY_RUN[flag], requested_by


_provided: "tuple[EventBus, Any] | None" = None


def use_clients(bus: "EventBus", firestore_client: Any) -> None:
    """The bus and the Firestore client the process has already made (`platform-cli job`
    sets them before a job runs), so that a job makes no second client."""
    global _provided
    _provided = (bus, firestore_client)


def _clients() -> "tuple[EventBus, Any]":
    """The bus and the Firestore client of the job's project, as `use_clients` set them."""
    if _provided is None:
        raise RuntimeError("the job's clients were not set: run it as 'platform-cli job'")
    return _provided


class _WatchedRuns:
    """The run store, remembering the run started and the counts last handed to `finish`."""

    def __init__(self, runs: "RunStore") -> None:
        self._runs = runs
        self.run_id: str | None = None
        self.counts: dict[str, int] = {}

    def start(self, kind: RunKind, dry_run: bool, requested_by: RequestedBy, now: datetime) -> str:
        self.run_id = self._runs.start(kind, dry_run, requested_by, now)
        return self.run_id

    def finish(
        self,
        run_id: str,
        state: Literal["completed", "failed"],
        guard: Literal["passed", "blocked"] | None,
        counts: dict[str, int],
        now: datetime,
    ) -> None:
        self.counts = dict(counts)
        self._runs.finish(run_id, state, guard, counts, now)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runs, name)


def _set_up(settings: Settings, *, stripe: bool) -> tuple[bool, RequestedBy, _WatchedRuns]:
    from platform_api.commerce import adapters
    from platform_api.commerce.runtime import set_runtime
    from platform_api.commerce.settings import CommerceSettings
    from platform_api.shared.ratelimit import InMemoryRateLimiter

    dry_run, requested_by = _job_environment()
    commerce_settings = CommerceSettings()  # refuses the sandbox marker in prod
    key = None
    if stripe:
        name = os.environ.get("PLATFORM_STRIPE_KEY_SECRET", "").strip()
        if not name:
            raise SettingRefused
        key = adapters.read_secret(name)
    bus, client = _clients()
    runtime = adapters.build_runtime(
        commerce_settings, bus, client, stripe_key=key, limiter=InMemoryRateLimiter()
    )
    watched = _WatchedRuns(runtime.runs)
    runtime.runs = cast("RunStore", watched)
    set_runtime(runtime)
    return dry_run, requested_by, watched


def _finish_as_failed(watched: _WatchedRuns, run_id: str, now: datetime) -> None:
    try:
        held = watched.get(run_id)
        if held is None or held.state == "running":
            watched.finish(run_id, "failed", None, watched.counts, now)
    except Exception:  # noqa: S110  # the line printed already names the first failure
        pass


def _run(
    job: str, settings: Settings, work: Callable[[bool, RequestedBy, datetime], SyncRun]
) -> int:
    from platform_api.shared import clock

    try:
        dry_run, requested_by, watched = _set_up(settings, stripe=job == "stripe-reconcile")
    except Exception as exc:
        print(json.dumps({"job": job, "error": type(exc).__name__}))
        return 1
    now = clock.utcnow()
    try:
        run = work(dry_run, requested_by, now)
    except Exception as exc:
        if watched.run_id is None:  # the run was never started
            print(json.dumps({"job": job, "error": type(exc).__name__}))
            return 1
        print(json.dumps({"job": job, "run_id": watched.run_id, "error": type(exc).__name__}))
        _finish_as_failed(watched, watched.run_id, now)
        return 1
    print(run.model_dump_json())
    return exit_code(run)


def _stripe_reconcile(settings: Settings) -> int:
    from platform_api.commerce.reconcile import stripe_reconcile

    return _run("stripe-reconcile", settings, stripe_reconcile)


def _roster_import(settings: Settings) -> int:
    from platform_api.commerce.roster import roster_import

    # The import records the owner as the one who asked (`roster_import`); the variable is
    # still checked, so a value the job does not accept stops it as it stops the reconcile.
    return _run("roster-import", settings, lambda dry_run, _, now: roster_import(dry_run, now))


JOBS: dict[str, Callable[[Settings], int]] = {
    "stripe-reconcile": _stripe_reconcile,
    "roster-import": _roster_import,
}
