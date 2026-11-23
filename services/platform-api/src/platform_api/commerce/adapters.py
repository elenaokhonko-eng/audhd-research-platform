"""The cloud versions of the commerce ports: Firestore, Cloud Run, Cloud Storage, Secret Manager.

Collections (contracts section 4): `sync_runs/{auto}` (a `SyncRun` as it dumps),
`promotions/{promotion_id}`, `promotion_upgrades/{promotion_id}:{contact_id}`, and the
document `config/reconcile_slot` (the last start of each kind, for `acquire_start_slot`).

The feature modules may not import `platform_api.adapters` (`.importlinter`), so the small
transaction helper and the lazy client below follow Core's `in_transaction` and `Lazy`
without importing them. The stores ask the client for a collection on each use, so a lazy
client is not built until a store is used.

`sync_runs` is read with the three composite indexes of the Infra lane (`kind`;
`kind`, `state`, `dry_run`; `kind`, `dry_run`; each then `finished_at` descending) and
equality filters only; each query names the index that serves it. A run still running
has `finished_at` null, which Firestore sorts after every time when descending; running runs
are therefore read by equality filters alone and merged, newest first by finish time, or by
start time while unfinished, as the in-memory store orders them.

Importing this module does not import the Stripe library: only `build_runtime` with a key
does, so the api service never loads it.
"""

import logging
import threading
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, cast

from google.cloud import firestore
from google.cloud.firestore import FieldFilter, Increment

from platform_api.commerce.models import Promotion, RequestedBy, RunKind, SyncRun
from platform_api.commerce.ports import (
    JobStarter,
    JobStartError,
    PromotionStore,
    RosterInbox,
    RosterObject,
    RunStore,
    StripeReader,
)
from platform_api.commerce.runtime import Runtime
from platform_api.commerce.settings import CommerceSettings

if TYPE_CHECKING:
    from platform_api.shared.bus import EventBus
    from platform_api.shared.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

_GAVE_UP = "Failed to commit transaction"  # the start of the library's message


def _in_transaction[T](client: Any, work: Callable[[Any], T]) -> T:
    """As Core's `in_transaction`: a transaction that gives up is a RuntimeError, not the
    library's ValueError, which a route would answer as a refusal."""
    try:
        result: T = firestore.transactional(work)(client.transaction())
    except ValueError as exc:
        if str(exc).startswith(_GAVE_UP):
            raise RuntimeError("a Firestore transaction gave up after its retries") from exc
        raise
    return result


class _Lazy:
    """As Core's `Lazy`: an object built on first use, once."""

    def __init__(self, build: Callable[[], object]) -> None:
        self._build = build
        self._built: object | None = None
        self._lock = threading.Lock()

    def __getattr__(self, name: str) -> Any:
        if self._built is None:
            with self._lock:
                if self._built is None:
                    self._built = self._build()
        return getattr(self._built, name)


def _data(snapshot: Any) -> dict[str, Any] | None:
    if not snapshot.exists:
        return None
    found: dict[str, Any] | None = snapshot.to_dict()
    return found


def _newest_first(run: SyncRun) -> tuple[datetime, datetime, str]:
    return (run.finished_at or run.started_at, run.started_at, run.run_id)


# sync_runs


class FirestoreRunStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def _runs(self) -> Any:
        return self._client.collection("sync_runs")

    def _slot(self) -> Any:
        return self._client.collection("config").document("reconcile_slot")

    def start(self, kind: RunKind, dry_run: bool, requested_by: RequestedBy, now: datetime) -> str:
        ref = self._runs().document()
        run = SyncRun(
            run_id=ref.id,
            kind=kind,
            dry_run=dry_run,
            state="running",
            guard=None,
            requested_by=requested_by,
            counts={},
            started_at=now,
            finished_at=None,
        )
        ref.set(run.model_dump())
        return str(ref.id)

    def finish(
        self,
        run_id: str,
        state: Literal["completed", "failed"],
        guard: Literal["passed", "blocked"] | None,
        counts: dict[str, int],
        now: datetime,
    ) -> None:
        self._runs().document(run_id).update(
            {"state": state, "guard": guard, "counts": dict(counts), "finished_at": now}
        )

    def get(self, run_id: str) -> SyncRun | None:
        found = _data(self._runs().document(run_id).get())
        return SyncRun.model_validate(found) if found is not None else None

    def _query(self, **equal: object) -> Any:
        query = self._runs()
        for field, value in equal.items():
            query = query.where(filter=FieldFilter(field, "==", value))
        return query

    def _read(self, query: Any) -> list[SyncRun]:
        return [SyncRun.model_validate(s.to_dict()) for s in query.stream()]

    def _newest_finished(self, query: Any) -> Any:
        # Unfinished runs (finished_at null) come after every finished one in this order.
        return query.order_by("finished_at", direction=firestore.Query.DESCENDING)

    def _running(self, **equal: object) -> list[SyncRun]:
        # Equality filters only, no order: served by Firestore's single-field indexes.
        return self._read(self._query(**equal, state="running"))

    def recent(self, kind: RunKind | None, limit: int) -> list[SyncRun]:
        by_kind: dict[str, object] = {"kind": kind} if kind is not None else {}
        # Index sync_runs_by_kind (kind, finished_at desc); with no kind, the single-field
        # index of finished_at.
        finished = self._read(self._newest_finished(self._query(**by_kind)).limit(limit))
        merged = {r.run_id: r for r in (*finished, *self._running(**by_kind))}
        return sorted(merged.values(), key=_newest_first, reverse=True)[:limit]

    def latest(
        self, kind: RunKind, *, completed_only: bool = False, real_only: bool = False
    ) -> SyncRun | None:
        if completed_only and real_only:
            # Index sync_runs_by_kind_state_dry_run (kind, state, dry_run, finished_at desc).
            query = self._query(kind=kind, state="completed", dry_run=False)
            found = self._read(self._newest_finished(query).limit(1))
            return found[0] if found else None
        if real_only:
            # Index sync_runs_by_kind_dry_run (kind, dry_run, finished_at desc), merged with
            # the real runs still running, which that order puts last.
            query = self._query(kind=kind, dry_run=False)
            candidates = [
                *self._read(self._newest_finished(query).limit(1)),
                *self._running(kind=kind, dry_run=False),
            ]
            return max(candidates, key=_newest_first) if candidates else None
        if completed_only:
            # No caller asks for this. Index sync_runs_by_kind, read until the first completed.
            for snapshot in self._newest_finished(self._query(kind=kind)).stream():
                run = SyncRun.model_validate(snapshot.to_dict())
                if run.state == "completed":
                    return run
            return None
        found = self.recent(kind, 1)
        return found[0] if found else None

    def acquire_start_slot(self, kind: RunKind, now: datetime, gap: timedelta) -> bool:
        ref = self._slot()

        def work(transaction: Any) -> bool:
            held = _data(ref.get(transaction=transaction)) or {}
            last = held.get(kind)
            if last is not None and now - last < gap:
                return False
            transaction.set(ref, {**held, kind: now})
            return True

        return _in_transaction(self._client, work)


# promotions and promotion_upgrades

_DECLARED = frozenset(Promotion.model_fields)


class FirestorePromotionStore:
    def __init__(self, client: Any) -> None:
        self._client = client

    def _promotions(self) -> Any:
        return self._client.collection("promotions")

    def _upgrades(self) -> Any:
        return self._client.collection("promotion_upgrades")

    def list(self) -> list[Promotion]:
        found = []
        for snapshot in self._promotions().stream():
            data = snapshot.to_dict() or {}
            # The model forbids extra fields; a stored field it does not declare is left out.
            declared = {k: v for k, v in data.items() if k in _DECLARED}
            found.append(Promotion.model_validate({**declared, "id": snapshot.id}))
        return found

    def put_all(self, promotions: Sequence[Promotion]) -> None:
        refs = [(self._promotions().document(p.id), p) for p in promotions]

        def work(transaction: Any) -> None:
            stored = [ref.get(transaction=transaction).exists for ref, _ in refs]  # reads first
            for (ref, promotion), exists in zip(refs, stored, strict=True):
                data = promotion.model_dump(exclude={"id"})
                if exists:
                    del data["counts"]  # a stored id keeps its counts
                    transaction.update(ref, data)
                else:
                    transaction.set(ref, data)

        if refs:
            _in_transaction(self._client, work)

    def count_once(self, promotion_id: str, contact_id: str) -> bool:
        if not promotion_id or not contact_id or "/" in promotion_id + contact_id:
            raise ValueError("a promotion id and a contact id are names without '/'")
        if ":" in promotion_id:  # as `Promotion` refuses it: the key stays one per pair
            raise ValueError("a promotion id has no ':'")
        promotion = self._promotions().document(promotion_id)
        upgrade = self._upgrades().document(f"{promotion_id}:{contact_id}")

        def work(transaction: Any) -> bool:
            held = promotion.get(transaction=transaction).exists
            counted = upgrade.get(transaction=transaction).exists
            if not held or counted:
                return False
            transaction.create(upgrade, {"promotion_id": promotion_id, "contact_id": contact_id})
            transaction.update(promotion, {"counts.upgrades_in_window": Increment(1)})
            return True

        return _in_transaction(self._client, work)


# Cloud Run, Cloud Storage and Secret Manager


_START_TIMEOUT = 10  # seconds for the start request; a sign-in waits on it


class CloudRunJobStarter:
    """Starts one execution of a job and does not wait for it."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def start(self, job: str) -> None:
        from google.api_core.exceptions import GoogleAPIError
        from google.auth.exceptions import GoogleAuthError

        try:
            self._client.run_job(name=job, timeout=_START_TIMEOUT)
        except (GoogleAPIError, GoogleAuthError) as exc:
            # The library's text names the job and the caller's identity; it is not repeated.
            logger.warning("refresh_job_not_started error=%s", type(exc).__name__)
            raise JobStartError("the job could not be started") from None


class BucketRosterInbox:
    """The roster inbox: the most recently updated object of the bucket."""

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def newest(self) -> RosterObject | None:
        blobs = [
            b
            for b in self._client.list_blobs(self._bucket)
            if b.updated is not None and not b.name.endswith("/")
        ]
        if not blobs:
            return None
        newest = max(blobs, key=lambda b: b.updated)
        return RosterObject(
            name=newest.name, data=newest.download_as_bytes(), updated_at=newest.updated
        )


def _secrets_client() -> Any:
    from google.cloud import secretmanager

    return secretmanager.SecretManagerServiceClient()


def read_secret(name: str, *, client: Any = None) -> str:
    """The value of a Secret Manager secret: `name` is a version, or a secret whose latest
    version is read. The value is never logged and never put into an exception."""
    version = name if "/versions/" in name else f"{name}/versions/latest"
    try:
        found = (client or _secrets_client()).access_secret_version(name=version)
        value = found.payload.data.decode("utf-8").strip()
    except Exception as exc:  # the class only: neither the value nor the name
        raise RuntimeError(f"the secret could not be read ({type(exc).__name__})") from None
    if not value:
        raise RuntimeError("the secret is empty")
    return cast(str, value)


def _storage_client() -> Any:
    import google.cloud.storage as storage  # type: ignore[import-untyped]  # ships no types

    return storage.Client()


def _jobs_client() -> Any:
    from google.cloud import run_v2

    return run_v2.JobsClient()


def build_runtime(
    settings: CommerceSettings,
    bus: "EventBus",
    firestore_client: Any,
    *,
    stripe_key: str | None,
    limiter: "RateLimiter",
) -> Runtime:
    """The commerce runtime on the cloud ports. No client is built until a port is used.

    `stripe_key` None: no Stripe reader (the api service, whose identity cannot read the
    key). A job starter when `settings.reconcile_job` names a job; a roster inbox when
    `settings.roster_inbox_bucket` names a bucket. `firestore_client` and `limiter` are the
    caller's, so that the api service shares Core's.
    """
    stripe: StripeReader | None = None
    if stripe_key:
        # Only a job with the key imports the Stripe library; the api service never does.
        from platform_api.commerce.stripe_adapter import StripeSdkReader

        stripe = StripeSdkReader(stripe_key)
    jobs: JobStarter | None = (
        CloudRunJobStarter(_Lazy(_jobs_client)) if settings.reconcile_job else None
    )
    inbox: RosterInbox | None = (
        BucketRosterInbox(_Lazy(_storage_client), settings.roster_inbox_bucket)
        if settings.roster_inbox_bucket
        else None
    )
    runs: RunStore = FirestoreRunStore(firestore_client)
    promotions: PromotionStore = FirestorePromotionStore(firestore_client)
    return Runtime(
        settings=settings,
        stripe=stripe,
        runs=runs,
        bus=bus,
        inbox=inbox,
        jobs=jobs,
        limiter=limiter,
        promotions=promotions,
    )
