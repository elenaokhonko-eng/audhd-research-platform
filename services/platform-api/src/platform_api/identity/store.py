"""The storage port of the identity module, and an in-memory implementation."""

from typing import Protocol

from platform_api.identity.models import Member


class MemberStore(Protocol):
    def get(self, uid: str) -> Member | None: ...
    def put(self, member: Member) -> None: ...
    def count(self) -> int: ...


class InMemoryMemberStore:
    def __init__(self) -> None:
        self._members: dict[str, Member] = {}

    def get(self, uid: str) -> Member | None:
        found = self._members.get(uid)
        return found.model_copy(deep=True) if found else None

    def put(self, member: Member) -> None:
        self._members[member.uid] = member.model_copy(deep=True)

    def count(self) -> int:
        return len(self._members)
