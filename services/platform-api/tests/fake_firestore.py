"""A small in-process stand-in for the Firestore client, for unit tests of the adapters.

It covers only what the adapters call: documents (get, set, create, delete, update with
dotted paths and Increment), auto ids, equality and `in` filters, `order_by`, `count`, and
transactions run through the real `firestore.transactional` (with `abort_commits`, every
commit is aborted, so the transaction gives up as it would under endless contention). It does
not model conflicts between transactions or check that reads come before writes. It checks the adapters'
logic here; the emulator in CI checks their use of the real API.
"""

import copy
import itertools
from typing import Any

from google.api_core.exceptions import Aborted, AlreadyExists, NotFound
from google.cloud.firestore import Increment

_ids = itertools.count(1)


class Snapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data)


def _apply_update(data: dict[str, Any], changes: dict[str, Any]) -> None:
    for path, value in changes.items():
        parts = [p.strip("`") for p in path.split(".")]
        target = data
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        if isinstance(value, Increment):
            target[parts[-1]] = target.get(parts[-1], 0) + value.value
        else:
            target[parts[-1]] = copy.deepcopy(value)


class DocRef:
    def __init__(self, db: "FakeFirestore", collection: str, doc_id: str) -> None:
        self._db, self._collection, self.id = db, collection, doc_id

    @property
    def _key(self) -> tuple[str, str]:
        return (self._collection, self.id)

    def get(self, transaction: Any = None) -> Snapshot:
        self._db.reads.append(self._collection)
        return Snapshot(self.id, copy.deepcopy(self._db.docs.get(self._key)))

    def set(self, data: dict[str, Any]) -> None:
        self._db.writes.append(self._collection)
        self._db.docs[self._key] = copy.deepcopy(data)

    def create(self, data: dict[str, Any]) -> None:
        if self._key in self._db.docs:
            raise AlreadyExists("exists")
        self.set(data)

    def delete(self, data: Any = None) -> None:
        self._db.writes.append(self._collection)
        self._db.docs.pop(self._key, None)

    def update(self, changes: dict[str, Any]) -> None:
        if self._key not in self._db.docs:
            raise NotFound("missing")
        self._db.writes.append(self._collection)
        _apply_update(self._db.docs[self._key], changes)


class Query:
    def __init__(self, db: "FakeFirestore", collection: str, filters=(), order=None) -> None:
        self._db, self._collection, self._filters, self._order = db, collection, filters, order

    def where(self, *, filter: Any) -> "Query":
        return Query(self._db, self._collection, (*self._filters, filter), self._order)

    def order_by(self, field: str) -> "Query":
        return Query(self._db, self._collection, self._filters, field)

    def _value(self, data: dict[str, Any], path: str) -> Any:
        for part in path.split("."):
            if not isinstance(data, dict) or part not in data:
                return _MISSING
            data = data[part]
        return data

    def _matches(self, data: dict[str, Any]) -> bool:
        for f in self._filters:
            value = self._value(data, f.field_path)
            if f.op_string == "==" and value != f.value:
                return False
            if f.op_string == "in" and len(f.value) > 30:
                raise ValueError("an 'in' filter takes at most 30 values")
            if f.op_string == "in" and value not in f.value:
                return False
        return True

    def stream(self, transaction: Any = None) -> list[Snapshot]:
        self._db.reads.append(self._collection)
        found = [
            Snapshot(doc_id, copy.deepcopy(data))
            for (collection, doc_id), data in sorted(self._db.docs.items())
            if collection == self._collection and self._matches(data)
        ]
        if self._order is not None:
            found.sort(key=lambda s: self._value(s.to_dict() or {}, self._order))
        return found

    def count(self) -> "_Count":
        return _Count(len(self.stream()))


_MISSING = object()


class _Count:
    def __init__(self, n: int) -> None:
        self._n = n

    def get(self) -> list[list[Any]]:
        return [[type("Result", (), {"value": self._n})()]]


class Collection(Query):
    def document(self, doc_id: str | None = None) -> DocRef:
        return DocRef(self._db, self._collection, doc_id or f"auto{next(_ids):08d}")


class Transaction:
    """Enough of a transaction for `firestore.transactional`: writes apply at commit."""

    _read_only = False
    _max_attempts = 1

    def __init__(self, abort: bool = False) -> None:
        self._id: bytes | None = None
        self._staged: list[tuple[str, DocRef, dict[str, Any]]] = []
        self._abort = abort  # every commit is aborted, as under endless contention

    @property
    def in_progress(self) -> bool:
        return self._id is not None

    def _clean_up(self) -> None:
        self._id = None
        self._staged = []

    def _begin(self, retry_id: bytes | None = None) -> None:
        self._id = b"tx"

    def _commit(self) -> list[Any]:
        if self._abort:
            raise Aborted("contention")
        for kind, ref, data in self._staged:
            getattr(ref, kind)(data)
        self._clean_up()
        return []

    def _rollback(self) -> None:
        self._clean_up()

    def set(self, ref: DocRef, data: dict[str, Any]) -> None:
        self._staged.append(("set", ref, data))

    def create(self, ref: DocRef, data: dict[str, Any]) -> None:
        self._staged.append(("create", ref, data))

    def update(self, ref: DocRef, data: dict[str, Any]) -> None:
        self._staged.append(("update", ref, data))

    def delete(self, ref: DocRef) -> None:
        self._staged.append(("delete", ref, {}))


class FakeFirestore:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict[str, Any]] = {}
        self.reads: list[str] = []
        self.writes: list[str] = []
        self.abort_commits = False

    def collection(self, name: str) -> Collection:
        return Collection(self, name)

    def transaction(self) -> Transaction:
        return Transaction(abort=self.abort_commits)
