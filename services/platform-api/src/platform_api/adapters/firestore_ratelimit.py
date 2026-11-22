"""Rate limits on Firestore: `rate_limits/{key}:{window seconds}`, a window start and a count.

The key is a member uid and an action (for example `support:<uid>`), never an address.
A document also carries `expires_at`, the end of its window plus two days, for Firestore's
time-to-live policy.
"""

from datetime import UTC, datetime, timedelta

from google.cloud import firestore

from platform_api.adapters import in_transaction
from platform_api.shared.ratelimit import count_hit

LIMIT_AFTERLIFE = timedelta(days=2)  # `expires_at` is the end of the window plus this


class FirestoreRateLimiter:
    def __init__(self, client: firestore.Client) -> None:
        self._client = client
        self._limits = client.collection("rate_limits")

    def hit(self, key: str, limit: int, window: timedelta, now: datetime) -> int | None:
        if not key or "/" in key:
            raise ValueError("a rate-limit key is a non-empty name without '/'")
        size = window.total_seconds()
        ref = self._limits.document(f"{key}:{int(size)}")

        def work(transaction: firestore.Transaction) -> int | None:
            snapshot = ref.get(transaction=transaction)
            stored = snapshot.to_dict() if snapshot.exists else None
            held = (
                (stored["window_start"].timestamp(), int(stored["count"]))
                if stored is not None
                else None
            )
            (start, used), wait = count_hit(held, limit, window, now)
            if wait is None:
                window_start = datetime.fromtimestamp(start, UTC)
                transaction.set(
                    ref,
                    {
                        "window_start": window_start,
                        "count": used,
                        "expires_at": window_start + window + LIMIT_AFTERLIFE,
                    },
                )
            return wait

        return in_transaction(self._client, work)
