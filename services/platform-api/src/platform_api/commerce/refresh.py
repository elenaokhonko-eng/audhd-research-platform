"""'Check again': a fresh look at Stripe on request, one job at a time, limited per member."""

from datetime import datetime, timedelta
from typing import Literal

from platform_api.commerce.models import RefreshTicket, SyncRun
from platform_api.commerce.runtime import get_runtime

GAP = timedelta(seconds=60)  # a run completed this recently is fresh; one start per gap
# A run still `running` blocks a new start for at most this long after it started, so a run
# that crashed without finishing does not block "Check again" for ever. Tied to Infra's
# timeout of the stripe-reconcile job (540 s): a run still `running` after it was stopped.
RUNNING_BOUND = timedelta(minutes=10)
# After a real run the guard blocked, or one that failed, "Check again" (and a sign-in)
# starts nothing for this long: the same source would trip the same guard or fail the same
# way, and the owner has an alert to look at first.
BACKOFF = timedelta(minutes=15)
_LIMITS = (("m", 1, timedelta(minutes=1)), ("h", 6, timedelta(hours=1)))


class RateLimited(Exception):
    """The member asked too often. Carries the seconds to wait; never an id or an address."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after


def _checked_at(run: SyncRun | None) -> datetime | None:
    """When a completed real run finished, if its guard passed."""
    if run is None or run.guard != "passed":
        return None
    return run.finished_at


def last_reconcile_completed_at() -> datetime | None:
    """When the last real reconcile finished with its guard passed; a dry run does not count."""
    return _checked_at(
        get_runtime().runs.latest("stripe_reconcile", completed_only=True, real_only=True)
    )


def _within(run: SyncRun | None, window: timedelta, now: datetime) -> bool:
    return run is not None and run.finished_at is not None and now - run.finished_at < window


def request_refresh(uid: str | None, now: datetime) -> RefreshTicket:
    """Start the reconcile job unless a run completed in the last minute or one just started.

    A member (`uid`) is limited to one request a minute and six an hour; a sign-in (`uid`
    None) is not limited but shares the start slot. Raises RateLimited, or JobStartError
    when the job could not be started.
    """
    runtime = get_runtime()
    if uid is not None:
        for suffix, limit, window in _LIMITS:
            # The minute comes first: a request it refuses never counts toward the hour.
            wait = runtime.limiter.hit(f"refresh:{uid}:{suffix}", limit, window, now)
            if wait is not None:
                raise RateLimited(retry_after=wait)

    # Two reads per request: the latest completed real run, and the latest real run in any
    # state. The ticket's `last_completed_at` comes from the first.
    latest = runtime.runs.latest("stripe_reconcile", completed_only=True, real_only=True)
    current = runtime.runs.latest("stripe_reconcile", real_only=True)

    def ticket(check: Literal["fresh", "started", "already_running"]) -> RefreshTicket:
        return RefreshTicket(
            check=check, last_completed_at=_checked_at(latest), next_allowed_at=now + GAP
        )

    # Whatever its guard: a blocked run is not restarted at the floor rate.
    if _within(latest, GAP, now):
        return ticket("fresh")
    # A blocked guard or a failed run is not restarted for BACKOFF: one alert, not one a minute.
    if latest is not None and latest.guard == "blocked" and _within(latest, BACKOFF, now):
        return ticket("fresh")
    if current is not None and current.state == "failed" and _within(current, BACKOFF, now):
        return ticket("fresh")
    if runtime.jobs is None or not runtime.settings.reconcile_job:
        return ticket("fresh")
    if (
        current is not None
        and current.state == "running"
        and now - current.started_at < RUNNING_BOUND
    ):
        return ticket("already_running")
    if not runtime.runs.acquire_start_slot("stripe_reconcile", now, GAP):
        return ticket("already_running")
    # A start that raises JobStartError keeps the slot for GAP on purpose, as backoff: the
    # next requests in that minute answer already_running. Nothing is granted either way.
    runtime.jobs.start(runtime.settings.reconcile_job)
    return ticket("started")
