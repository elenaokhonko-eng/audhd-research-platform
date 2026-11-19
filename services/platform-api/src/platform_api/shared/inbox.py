"""Idempotency inbox: remember which event ids were handled."""

from datetime import datetime
from typing import Protocol

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore


class Inbox(Protocol):
    def seen(self, event_id: str) -> bool: ...

    def record(self, event_id: str, *, event_type: str, received_at: datetime) -> None:
        """Remember the id. Calling it twice is not an error."""
        ...


class InMemoryInbox:
    def __init__(self) -> None:
        self._ids: dict[str, str] = {}

    def seen(self, event_id: str) -> bool:
        return event_id in self._ids

    def record(self, event_id: str, *, event_type: str, received_at: datetime) -> None:
        self._ids.setdefault(event_id, event_type)


class FirestoreInbox:
    def __init__(self, client: firestore.Client, collection: str = "inbox") -> None:
        self._client = client
        self._collection = collection

    def seen(self, event_id: str) -> bool:
        snapshot = self._client.collection(self._collection).document(event_id).get()
        return bool(snapshot.exists)

    def record(self, event_id: str, *, event_type: str, received_at: datetime) -> None:
        try:
            self._client.collection(self._collection).document(event_id).create(
                {"event_type": event_type, "received_at": received_at}
            )
        except AlreadyExists:
            return
