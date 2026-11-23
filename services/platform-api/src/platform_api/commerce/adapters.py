"""The cloud versions of the commerce ports: Firestore, Cloud Run, Cloud Storage, Secret Manager.

Collections (contracts section 4): `sync_runs/{auto}` (a `SyncRun` as it dumps),
`promotions/{promotion_id}`, `promotion_upgrades/{promotion_id}:{contact_id}`, and the
document `config/reconcile_slot` (the last start of each kind, for `acquire_start_slot`).

The feature modules may not import `platform_api.adapters` (`.importlinter`), so the small
transaction helper and the lazy client below follow Core's `in_transaction` and `Lazy`
without importing them. The stores ask the client for a collection on each use, so a lazy
client is not built until a store is used.

`sync_runs` is read with the composite indexes of the Infra lane: (`kind`, `finished_at`
descending) and (`kind`, `state`, `dry_run`, `finished_at` descending). A run still running
has `finished_at` null, which Firestore sorts after every time when descending; running runs
are therefore read by equality filters alone and merged, newest first by finish time, or by
start time while unfinished, as the in-memory store orders them.
"""

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
from platform_api.commerce.stripe_adapter import StripeSdkReader

if TYPE_CHECKING:
    from platform_api.shared.bus import EventBus
    from platform_api.shared.ratelimit import RateLimiter

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
            if isinstance(value, list):
                query = query.where(filter=FieldFilter(field, "in", value))
            else:
                query = query.where(filter=FieldFilter(field, "==", value))
        return query

    def _read(self, query: Any) -> list[SyncRun]:
        return [SyncRun.model_validate(s.to_dict()) for s in query.stream()]

    def _finished_first(self, query: Any, limit: int) -> list[SyncRun]:
        ordered = query.order_by("finished_at", direction=firestore.Query.DESCENDING)
        return self._read(ordered.limit(limit))

    def recent(self, kind: RunKind | None, limit: int) -> list[SyncRun]:
        by_kind: dict[str, object] = {"kind": kind} if kind is not None else {}
        # index (kind, finished_at desc), or the single-field index when no kind is named
        finished = self._finished_first(self._query(**by_kind), limit)
        running = self._read(self._query(**by_kind, state="running"))  # equality only
        merged = {r.run_id: r for r in (*finished, *running)}
        return sorted(merged.values(), key=_newest_first, reverse=True)[:limit]

    def latest(
        self, kind: RunKind, *, completed_only: bool = False, real_only: bool = False
    ) -> SyncRun | None:
        if not completed_only and not real_only:
            found = self.recent(kind, 1)
            return found[0] if found else None
        dry_runs: object = False if real_only else [False, True]
        states: object = "completed" if completed_only else ["completed", "failed"]
        # index (kind, state, dry_run, finished_at desc)
        candidates = self._finished_first(self._query(kind=kind, state=states, dry_run=dry_runs), 1)
        if not completed_only:
            running = {"kind": kind, "state": "running", "dry_run": False}  # equality only
            candidates += self._read(self._query(**running))
        return max(candidates, key=_newest_first) if candidates else None

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


class CloudRunJobStarter:
    """Starts one execution of a job and does not wait for it."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def start(self, job: str) -> None:
        from google.api_core.exceptions import GoogleAPIError
        from google.auth.exceptions import GoogleAuthError

        try:
            self._client.run_job(name=job)
        except (GoogleAPIError, GoogleAuthError):
            # The library's text names the job and the caller's identity; it is not repeated.
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
    except Exception:
        raise RuntimeError("the secret could not be read") from None
    if not value:
        raise RuntimeError("the secret is empty")
    return cast(str, value)


def _storage_client() -> Any:
    from google.cloud import storage  # type: ignore[attr-defined]

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
    stripe: StripeReader | None = StripeSdkReader(stripe_key) if stripe_key else None
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
