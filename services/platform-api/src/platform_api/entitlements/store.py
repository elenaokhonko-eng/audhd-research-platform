"""The storage port of the entitlements module, and an in-memory implementation."""

from collections.abc import Sequence
from typing import Protocol

from platform_api.entitlements.models import AuditEntry, Contact, Entitlement, Source


class EntitlementStore(Protocol):
    def get_contact(self, contact_id: str) -> Contact | None: ...
    def put_contact(self, contact: Contact) -> None: ...
    def contact_ids_for_member(self, uid: str) -> list[str]: ...
    def entitlements_for_contacts(self, contact_ids: Sequence[str]) -> list[Entitlement]: ...
    def entitlements_for_member(self, uid: str) -> list[Entitlement]: ...
    def entitlements_by_source(self, source: Source) -> list[Entitlement]: ...
    def get_entitlement(self, entitlement_id: str) -> Entitlement | None: ...
    def write(
        self, contact_id: str, entitlements: Sequence[Entitlement], audit: Sequence[AuditEntry]
    ) -> None:
        """One atomic unit per contact: all of it or none.

        Every entitlement's `contact_id` must equal the `contact_id` argument; otherwise
        ValueError is raised and nothing is written (neither entitlements nor audit entries).
        """
        ...

    def create_if_absent(self, entitlement: Entitlement, audit: AuditEntry) -> bool:
        """False when the id already exists."""
        ...

    def audit_for(self, subject: str) -> list[AuditEntry]: ...


class InMemoryStore:
    """Copies models on the way in and out, so a caller cannot change stored state."""

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._entitlements: dict[str, Entitlement] = {}
        self._audit: list[AuditEntry] = []

    def get_contact(self, contact_id: str) -> Contact | None:
        found = self._contacts.get(contact_id)
        return found.model_copy(deep=True) if found else None

    def put_contact(self, contact: Contact) -> None:
        self._contacts[contact.contact_id] = contact.model_copy(deep=True)

    def contact_ids_for_member(self, uid: str) -> list[str]:
        return [
            cid
            for cid, c in self._contacts.items()
            if c.channels.get("platform", {}).get("member_uid") == uid
        ]

    def entitlements_for_contacts(self, contact_ids: Sequence[str]) -> list[Entitlement]:
        wanted = set(contact_ids)
        return [e.model_copy() for e in self._entitlements.values() if e.contact_id in wanted]

    def entitlements_for_member(self, uid: str) -> list[Entitlement]:
        return [e.model_copy() for e in self._entitlements.values() if e.member_uid == uid]

    def entitlements_by_source(self, source: Source) -> list[Entitlement]:
        return [e.model_copy() for e in self._entitlements.values() if e.source == source]

    def get_entitlement(self, entitlement_id: str) -> Entitlement | None:
        found = self._entitlements.get(entitlement_id)
        return found.model_copy() if found else None

    def write(
        self, contact_id: str, entitlements: Sequence[Entitlement], audit: Sequence[AuditEntry]
    ) -> None:
        if any(e.contact_id != contact_id for e in entitlements):
            raise ValueError("every record in one write belongs to one contact")
        staged = [e.model_copy() for e in entitlements]
        staged_audit = [a.model_copy(deep=True) for a in audit]
        for e in staged:
            self._entitlements[e.entitlement_id] = e
        self._audit.extend(staged_audit)

    def create_if_absent(self, entitlement: Entitlement, audit: AuditEntry) -> bool:
        if entitlement.entitlement_id in self._entitlements:
            return False
        self._entitlements[entitlement.entitlement_id] = entitlement.model_copy()
        self._audit.append(audit.model_copy(deep=True))
        return True

    def audit_for(self, subject: str) -> list[AuditEntry]:
        return [a.model_copy(deep=True) for a in self._audit if a.subject == subject]
