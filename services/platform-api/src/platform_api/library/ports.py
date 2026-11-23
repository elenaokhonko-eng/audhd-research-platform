"""Where the library keeps its records and files, with in-memory versions for tests."""

import hashlib
from datetime import datetime, timedelta
from typing import Protocol

from platform_api.library.models import LibraryItem


class ItemStore(Protocol):
    def get(self, sku: str) -> LibraryItem | None: ...
    def list_all(self) -> list[LibraryItem]: ...
    def put(self, item: LibraryItem) -> None: ...


class FileStore(Protocol):
    def list_dirs(self, prefix: str) -> list[str]:
        """The folder names directly under `prefix + "/"`."""
        ...

    def read(self, path: str) -> bytes | None: ...
    def exists(self, path: str) -> bool: ...
    def sha256(self, path: str) -> str | None: ...

    def create_from(self, source: "FileStore", src: str, dst: str) -> bool:
        """Copy `src` of `source` to `dst` only if `dst` does not exist; say whether it did."""
        ...

    def signed_url(self, path: str, ttl: timedelta, now: datetime) -> str: ...


class DownloadLog(Protocol):
    def add(self, member_uid: str, sku: str, version: str, at: datetime) -> None: ...

    def times_since(self, member_uid: str, since: datetime) -> list[datetime]:
        """The member's downloads with `at > since`, oldest first."""
        ...


class InMemoryItemStore:
    def __init__(self) -> None:
        self.items: dict[str, LibraryItem] = {}

    def get(self, sku: str) -> LibraryItem | None:
        item = self.items.get(sku)
        return item.model_copy(deep=True) if item else None

    def list_all(self) -> list[LibraryItem]:
        return [self.items[sku].model_copy(deep=True) for sku in sorted(self.items)]

    def put(self, item: LibraryItem) -> None:
        self.items[item.sku] = item.model_copy(deep=True)


class InMemoryFileStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def list_dirs(self, prefix: str) -> list[str]:
        start = prefix + "/"
        names = {
            path[len(start) :].split("/", 1)[0]
            for path in self.objects
            if path.startswith(start) and "/" in path[len(start) :]
        }
        return sorted(names)

    def read(self, path: str) -> bytes | None:
        return self.objects.get(path)

    def exists(self, path: str) -> bool:
        return path in self.objects

    def sha256(self, path: str) -> str | None:
        data = self.objects.get(path)
        return hashlib.sha256(data).hexdigest() if data is not None else None

    def create_from(self, source: FileStore, src: str, dst: str) -> bool:
        if dst in self.objects:
            return False
        data = source.read(src)
        if data is None:
            raise FileNotFoundError(src)
        self.objects[dst] = data
        return True

    def signed_url(self, path: str, ttl: timedelta, now: datetime) -> str:
        return f"https://files.invalid/{path}?expires={int((now + ttl).timestamp())}"


class InMemoryDownloadLog:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str, str, datetime]] = []

    def add(self, member_uid: str, sku: str, version: str, at: datetime) -> None:
        self.entries.append((member_uid, sku, version, at))

    def times_since(self, member_uid: str, since: datetime) -> list[datetime]:
        return sorted(at for uid, _, _, at in self.entries if uid == member_uid and at > since)
