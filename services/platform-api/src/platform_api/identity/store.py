"""The storage port of the identity module, and an in-memory implementation."""

from collections.abc import Callable
from typing import Literal, Protocol

from platform_api.identity.models import Member, SupportRequest

MemberChange = Callable[[Member | None], Member | None]
Status = Literal["active", "deletion_requested"]


class MemberStore(Protocol):
    def get(self, uid: str) -> Member | None: ...
    def put(self, member: Member) -> None:
        """Overwrites the member. Code that changes a stored member uses `merge_member`."""
        ...

    def merge_member(self, uid: str, change: MemberChange) -> Member | None:
        """Change one member in one atomic step and return it as stored afterwards.

        `change` gets the stored member (None when there is none) and returns the new member,
        or None to leave it as it is. No other write to the member can come between the read
        and the write. `change` may be called more than once (a Firestore transaction is
        retried), so it must not have side effects. ValueError when the member it returns
        has another uid; nothing is written then.
        """
        ...

    def create_if_absent(self, member: Member) -> bool:
        """Store a new member in one atomic step. False, and nothing written, when the uid
        exists already (another sign-in created it first)."""
        ...

    def delete(self, uid: str) -> bool:
        """Remove the member. False, and nothing changed, when there is none."""
        ...

    def members_with_status(self, status: Status) -> list[Member]:
        """Every member with this status, in no particular order."""
        ...

    def count(self) -> int: ...
    def add_support_request(self, request: SupportRequest) -> None: ...
    def support_requests(self) -> list[SupportRequest]: ...
    def delete_support_requests(self, uid: str) -> int:
        """Remove every request of the member; the number removed."""
        ...


class InMemoryMemberStore:
    def __init__(self) -> None:
        self._members: dict[str, Member] = {}
        self._support: list[SupportRequest] = []

    def get(self, uid: str) -> Member | None:
        found = self._members.get(uid)
        return found.model_copy(deep=True) if found else None

    def put(self, member: Member) -> None:
        self._members[member.uid] = member.model_copy(deep=True)

    def merge_member(self, uid: str, change: MemberChange) -> Member | None:
        held = self.get(uid)
        changed = change(held)
        if changed is None:
            return held
        if changed.uid != uid:
            raise ValueError("a change may not move a member to another uid")
        self.put(changed)
        return self.get(uid)

    def create_if_absent(self, member: Member) -> bool:
        if member.uid in self._members:
            return False
        self.put(member)
        return True

    def delete(self, uid: str) -> bool:
        return self._members.pop(uid, None) is not None

    def members_with_status(self, status: Status) -> list[Member]:
        return [m.model_copy(deep=True) for m in self._members.values() if m.status == status]

    def count(self) -> int:
        return len(self._members)

    def add_support_request(self, request: SupportRequest) -> None:
        self._support.append(request.model_copy(deep=True))

    def support_requests(self) -> list[SupportRequest]:
        """Oldest first."""
        return [r.model_copy(deep=True) for r in self._support]

    def delete_support_requests(self, uid: str) -> int:
        kept = [r for r in self._support if r.member_uid != uid]
        removed = len(self._support) - len(kept)
        self._support = kept
        return removed
