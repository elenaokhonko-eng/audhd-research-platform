"""The commerce jobs, run as `platform-cli job <name>` (contracts section 6).

Each job builds the commerce runtime from the cloud adapters, reads
`PLATFORM_JOB_DRY_RUN` (`1` is a dry run; unset, empty or `0` a real one; anything else
stops the job) and `PLATFORM_JOB_REQUESTED_BY` (default `schedule`), runs once at
`clock.utcnow()`, and prints the run as one JSON line: counts only, never an address.

Exit codes: 0 completed with the guard passed; 1 failed; 2 completed with the guard
blocked. A job that cannot start (a setting refused, the secret unreadable, a client that
cannot be built) prints one line naming the exception's class and exits 1; it stops before
a run is started, so none is left `running`.

Only `stripe-reconcile` reads the Stripe key, from the Secret Manager name in
`PLATFORM_STRIPE_KEY_SECRET`. Importing this module creates no cloud client.
"""

import json
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from platform_api.commerce.models import RequestedBy, SyncRun
from platform_api.settings import Settings

if TYPE_CHECKING:
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


def _clients(settings: Settings) -> "tuple[EventBus, Any]":
    """The bus and the Firestore client of the job's project."""
    from google.cloud import firestore
    from google.cloud.pubsub_v1 import PublisherClient  # type: ignore[import-untyped]

    from platform_api.shared.bus import PubSubBus

    bus = PubSubBus(PublisherClient(), settings.gcp_project, settings.events_topic)
    return bus, firestore.Client(project=settings.gcp_project)


def _set_up(settings: Settings, *, stripe: bool) -> tuple[bool, RequestedBy]:
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
    bus, client = _clients(settings)
    runtime = adapters.build_runtime(
        commerce_settings, bus, client, stripe_key=key, limiter=InMemoryRateLimiter()
    )
    set_runtime(runtime)
    return dry_run, requested_by


def _run(job: str, settings: Settings, work: Callable[[bool, RequestedBy], SyncRun]) -> int:
    try:
        dry_run, requested_by = _set_up(settings, stripe=job == "stripe-reconcile")
        run = work(dry_run, requested_by)
    except Exception as exc:
        print(json.dumps({"job": job, "error": type(exc).__name__}))
        return 1
    print(run.model_dump_json())
    return exit_code(run)


def _stripe_reconcile(settings: Settings) -> int:
    from platform_api.commerce.reconcile import stripe_reconcile
    from platform_api.shared import clock

    return _run(
        "stripe-reconcile",
        settings,
        lambda dry_run, requested_by: stripe_reconcile(dry_run, requested_by, clock.utcnow()),
    )


def _roster_import(settings: Settings) -> int:
    from platform_api.commerce.roster import roster_import
    from platform_api.shared import clock

    # The import records the owner as the one who asked (`roster_import`); the variable is
    # still checked, so a value the job does not accept stops it as it stops the reconcile.
    return _run(
        "roster-import", settings, lambda dry_run, _: roster_import(dry_run, clock.utcnow())
    )


JOBS: dict[str, Callable[[Settings], int]] = {
    "stripe-reconcile": _stripe_reconcile,
    "roster-import": _roster_import,
}
