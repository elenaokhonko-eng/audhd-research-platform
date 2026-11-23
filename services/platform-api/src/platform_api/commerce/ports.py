import uuid
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from platform_api.commerce.models import RequestedBy, RunKind, StripeSubscription, SyncRun


class StripeReadError(Exception):
    """Stripe could not be read to the end. Carries no detail that could hold an address."""


class StripeReader(Protocol):
    def subscriptions(self) -> Iterator[StripeSubscription]:
        """Every status, every page. Raises StripeReadError."""
        ...


class RunStore(Protocol):
    def start(
        self, kind: RunKind, dry_run: bool, requested_by: RequestedBy, now: datetime
    ) -> str: ...

    def finish(
        self,
        run_id: str,
        state: Literal["completed", "failed"],
        guard: Literal["passed", "blocked"] | None,
        counts: dict[str, int],
        now: datetime,
    ) -> None: ...

    def latest(
        self, kind: RunKind, *, completed_only: bool = False, real_only: bool = False
    ) -> SyncRun | None: ...

    def recent(self, kind: RunKind | None, limit: int) -> list[SyncRun]: ...

    def get(self, run_id: str) -> SyncRun | None: ...

    def acquire_start_slot(self, kind: RunKind, now: datetime, gap: timedelta) -> bool:
        """Atomic. True, and `now` recorded as the last start, when no slot of `kind` was
        taken within `gap` before `now`; otherwise False and nothing recorded."""
        ...


class JobStartError(Exception):
    """A job could not be started. Carries no id and no address."""


class JobStarter(Protocol):
    def start(self, job: str) -> None:
        """Start one execution of the job named by its full resource name. Raises JobStartError."""
        ...


class InMemoryJobStarter:
    def __init__(self) -> None:
        self.started: list[str] = []

    def start(self, job: str) -> None:
        self.started.append(job)


class RosterObject(BaseModel):
    """The owner's export file as found in the roster inbox. Its bytes are never shown."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    name: str
    data: bytes = Field(repr=False)
    updated_at: AwareDatetime


class RosterInbox(Protocol):
    def newest(self) -> RosterObject | None:
        """The most recently placed export, or None when the inbox is empty."""
        ...


class InMemoryRosterInbox:
    def __init__(self, *objects: RosterObject) -> None:
        self._objects = list(objects)

    def newest(self) -> RosterObject | None:
        if not self._objects:
            return None
        return max(self._objects, key=lambda o: o.updated_at)


class InMemoryStripeReader:
    def __init__(self, subs: Iterable[StripeSubscription], fail_after: int | None = None) -> None:
        self._subs = list(subs)
        self._fail_after = fail_after

    def subscriptions(self) -> Iterator[StripeSubscription]:
        for i, sub in enumerate(self._subs):
            if self._fail_after is not None and i >= self._fail_after:
                raise StripeReadError("read failed")
            yield sub
        if self._fail_after is not None and self._fail_after >= len(self._subs):
            raise StripeReadError("read failed")


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, SyncRun] = {}
        self._last_start: dict[RunKind, datetime] = {}

    def acquire_start_slot(self, kind: RunKind, now: datetime, gap: timedelta) -> bool:
        last = self._last_start.get(kind)
        if last is not None and now - last < gap:
            return False
        self._last_start[kind] = now
        return True

    def start(self, kind: RunKind, dry_run: bool, requested_by: RequestedBy, now: datetime) -> str:
        run_id = uuid.uuid4().hex
        self._runs[run_id] = SyncRun(
            run_id=run_id,
            kind=kind,
            dry_run=dry_run,
            state="running",
            guard=None,
            requested_by=requested_by,
            counts={},
            started_at=now,
            finished_at=None,
        )
        return run_id

    def finish(
        self,
        run_id: str,
        state: Literal["completed", "failed"],
        guard: Literal["passed", "blocked"] | None,
        counts: dict[str, int],
        now: datetime,
    ) -> None:
        self._runs[run_id] = self._runs[run_id].model_copy(
            update={"state": state, "guard": guard, "counts": dict(counts), "finished_at": now}
        )

    def get(self, run_id: str) -> SyncRun | None:
        return self._runs.get(run_id)

    def recent(self, kind: RunKind | None, limit: int) -> list[SyncRun]:
        # newest first by finish time (start time while unfinished); ties go to the later insert
        order = {run_id: i for i, run_id in enumerate(self._runs)}
        runs = [r for r in self._runs.values() if kind is None or r.kind == kind]
        runs.sort(key=lambda r: (r.finished_at or r.started_at, order[r.run_id]), reverse=True)
        return runs[:limit]

    def latest(
        self, kind: RunKind, *, completed_only: bool = False, real_only: bool = False
    ) -> SyncRun | None:
        runs = [
            r
            for r in self.recent(kind, len(self._runs))
            if (not completed_only or r.state == "completed") and (not real_only or not r.dry_run)
        ]
        return runs[0] if runs else None
