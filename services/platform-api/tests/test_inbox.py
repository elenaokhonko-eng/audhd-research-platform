from datetime import UTC, datetime
from typing import Any

import pytest
from google.api_core.exceptions import AlreadyExists

from platform_api.shared.inbox import FirestoreInbox, InMemoryInbox

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def test_inbox_remembers_and_tolerates_repeats() -> None:
    inbox = InMemoryInbox()
    assert inbox.seen("e1") is False
    inbox.record("e1", event_type="t", received_at=NOW)
    inbox.record("e1", event_type="t", received_at=NOW)
    assert inbox.seen("e1") is True
    assert inbox.seen("e2") is False


class _Doc:
    def __init__(self, store: dict[str, dict[str, Any]], doc_id: str) -> None:
        self._store, self._id = store, doc_id

    def create(self, data: dict[str, Any]) -> None:
        if self._id in self._store:
            raise AlreadyExists("exists")
        self._store[self._id] = data

    def get(self) -> Any:
        exists = self._id in self._store
        return type("Snap", (), {"exists": exists})()


class _Collection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _Doc:
        return _Doc(self._store, doc_id)


class _FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.names: list[str] = []

    def collection(self, name: str) -> _Collection:
        self.names.append(name)
        return _Collection(self.store)


def test_firestore_inbox_tolerates_a_second_record_and_reads_exists() -> None:
    client = _FakeClient()
    inbox = FirestoreInbox(client, "inbox")  # type: ignore[arg-type]
    assert inbox.seen("e1") is False
    inbox.record("e1", event_type="t", received_at=NOW)
    inbox.record("e1", event_type="t", received_at=NOW)  # AlreadyExists is swallowed
    assert inbox.seen("e1") is True
    assert client.store["e1"]["event_type"] == "t"
    assert set(client.names) == {"inbox"}


def test_firestore_inbox_lets_other_errors_through() -> None:
    class Boom(_FakeClient):
        def collection(self, name: str) -> Any:
            raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        FirestoreInbox(Boom(), "inbox").record(  # type: ignore[arg-type]
            "e1", event_type="t", received_at=NOW
        )
