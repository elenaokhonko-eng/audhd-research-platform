"""The storage port of the identity module, and an in-memory implementation."""

from typing import Protocol

from platform_api.identity.models import Member, SupportRequest


class MemberStore(Protocol):
    def get(self, uid: str) -> Member | None: ...
    def put(self, member: Member) -> None: ...
    def create_if_absent(self, member: Member) -> bool:
        """Store a new member in one atomic step. False, and nothing written, when the uid
        exists already (another sign-in created it first)."""
        ...

    def count(self) -> int: ...
    def add_support_request(self, request: SupportRequest) -> None: ...
    def support_requests(self) -> list[SupportRequest]: ...


class InMemoryMemberStore:
    def __init__(self) -> None:
        self._members: dict[str, Member] = {}
        self._support: list[SupportRequest] = []

    def get(self, uid: str) -> Member | None:
        found = self._members.get(uid)
        return found.model_copy(deep=True) if found else None

    def put(self, member: Member) -> None:
        self._members[member.uid] = member.model_copy(deep=True)

    def create_if_absent(self, member: Member) -> bool:
        if member.uid in self._members:
            return False
        self.put(member)
        return True

    def count(self) -> int:
        return len(self._members)

    def add_support_request(self, request: SupportRequest) -> None:
        self._support.append(request.model_copy(deep=True))

    def support_requests(self) -> list[SupportRequest]:
        """Oldest first."""
        return [r.model_copy(deep=True) for r in self._support]
