"""The storage port of the entitlements module, and an in-memory implementation."""

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol

from platform_api.entitlements.models import (
    AuditEntry,
    Campaign,
    Contact,
    Entitlement,
    LaunchConfig,
    Source,
)

ContactChange = Callable[[Contact | None], Contact | None]
ForgetAudit = Callable[[int], AuditEntry]  # the entry of a forgotten contact, from the count


def claimed_audit(entitlement_id: str, contact_id: str, uid: str, now: datetime) -> AuditEntry:
    """The audit entry of one record that `claim_records` claimed."""
    return AuditEntry(
        at=now,
        actor=f"member:{uid}",
        action="entitlement.claimed",
        subject=entitlement_id,
        reason=None,
        evidence={"contact_id": contact_id},
    )


def check_write(contact_id: str, entitlements: Sequence[Entitlement]) -> None:
    """The rule of `write`, checked by every store before it writes anything."""
    if not contact_id and entitlements:
        raise ValueError("records need a contact; only audit entries may go without one")
    if any(e.contact_id != contact_id for e in entitlements):
        raise ValueError("every record in one write belongs to one contact")


class EntitlementStore(Protocol):
    def get_contact(self, contact_id: str) -> Contact | None: ...
    def put_contact(self, contact: Contact) -> None:
        """Overwrites the contact. Code that changes a stored contact uses `merge_contact`."""
        ...

    def merge_contact(self, contact_id: str, change: ContactChange) -> Contact | None:
        """Change one contact in one atomic step and return it as stored afterwards.

        `change` gets the stored contact (None when there is none) and returns the new
        contact, or None to leave it as it is. No other write to the contact can come between
        the read and the write. `change` may be called more than once (a Firestore
        transaction is retried), so it must not have side effects. ValueError when the
        contact it returns has another id; nothing is written then.
        """
        ...

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

        `write("", [], entries)`, an empty contact_id with no entitlements, appends the audit
        entries only and touches no contact. An empty contact_id with any entitlement is
        refused with ValueError and nothing is written.
        """
        ...

    def create_if_absent(self, entitlement: Entitlement, audit: AuditEntry) -> bool:
        """False when the id already exists."""
        ...

    def claim_records(self, contact_id: str, uid: str, now: datetime) -> list[str]:
        """Give the member every record of the contact that no member holds yet, in one step.

        Reads each entitlement of the contact again, inside the step. A record whose
        `member_uid` is still None gets `member_uid = uid`, `updated_at = now` and
        `updated_by = "member:<uid>"`; its status and every other field stay as stored, so a
        record a run ended meanwhile stays ended. One `entitlement.claimed` audit entry per
        record claimed is written in the same step. Returns the ids claimed.
        """
        ...

    def forget_contact(self, contact_id: str, audit: ForgetAudit) -> int | None:
        """Delete the contact and every entitlement of it, in one atomic step.

        `audit(n)`, with n the number of entitlements deleted, is the entry written in the
        same step. It may be called more than once (a Firestore transaction is retried), so
        it must not have side effects. Returns n; None, with nothing deleted and nothing
        written, when the contact does not exist. Audit entries about the contact's records
        stay, to expire with the audit log.
        """
        ...

    def audit_for(self, subject: str) -> list[AuditEntry]: ...
    def get_campaign(self, slug: str) -> Campaign | None: ...
    def list_campaigns(self) -> list[Campaign]: ...
    def put_campaigns(self, campaigns: Sequence[Campaign]) -> None:
        """Writes each campaign under its slug; campaigns not named stay.

        A slug already stored keeps its stored counts (only `add_to_campaign_count` changes
        them); a new slug starts with the counts given.
        """
        ...

    def add_to_campaign_count(self, slug: str, key: str, by: int = 1) -> None:
        """Atomic increment; a missing key starts at zero. LookupError for an unknown slug."""
        ...

    def get_launch_config(self) -> LaunchConfig:
        """The stored switches, or the defaults (everything closed) when none are stored."""
        ...

    def put_launch_config(self, config: LaunchConfig) -> None: ...


class InMemoryStore:
    """Copies models on the way in and out, so a caller cannot change stored state."""

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._entitlements: dict[str, Entitlement] = {}
        self._audit: list[AuditEntry] = []
        self._campaigns: dict[str, Campaign] = {}
        self._launch = LaunchConfig()

    def get_contact(self, contact_id: str) -> Contact | None:
        found = self._contacts.get(contact_id)
        return found.model_copy(deep=True) if found else None

    def put_contact(self, contact: Contact) -> None:
        self._contacts[contact.contact_id] = contact.model_copy(deep=True)

    def merge_contact(self, contact_id: str, change: ContactChange) -> Contact | None:
        held = self.get_contact(contact_id)
        changed = change(held)
        if changed is None:
            return held
        if changed.contact_id != contact_id:
            raise ValueError("a change may not move a contact to another id")
        self.put_contact(changed)
        return self.get_contact(contact_id)

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
        check_write(contact_id, entitlements)
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

    def claim_records(self, contact_id: str, uid: str, now: datetime) -> list[str]:
        claimed = [
            e.model_copy(
                update={"member_uid": uid, "updated_at": now, "updated_by": f"member:{uid}"}
            )
            for e in self._entitlements.values()
            if e.contact_id == contact_id and e.member_uid is None
        ]
        for e in claimed:
            self._entitlements[e.entitlement_id] = e
            self._audit.append(claimed_audit(e.entitlement_id, contact_id, uid, now))
        return [e.entitlement_id for e in claimed]

    def forget_contact(self, contact_id: str, audit: ForgetAudit) -> int | None:
        if contact_id not in self._contacts:
            return None
        gone = [eid for eid, e in self._entitlements.items() if e.contact_id == contact_id]
        entry = audit(len(gone))
        for eid in gone:
            del self._entitlements[eid]
        del self._contacts[contact_id]
        self._audit.append(entry.model_copy(deep=True))
        return len(gone)

    def audit_for(self, subject: str) -> list[AuditEntry]:
        return [a.model_copy(deep=True) for a in self._audit if a.subject == subject]

    def get_campaign(self, slug: str) -> Campaign | None:
        found = self._campaigns.get(slug)
        return found.model_copy(deep=True) if found else None

    def list_campaigns(self) -> list[Campaign]:
        return [c.model_copy(deep=True) for c in self._campaigns.values()]

    def put_campaigns(self, campaigns: Sequence[Campaign]) -> None:
        for c in campaigns:
            held = self._campaigns.get(c.slug)
            kept = c.model_copy(update={"counts": dict(held.counts)}) if held else c
            self._campaigns[c.slug] = kept.model_copy(deep=True)

    def add_to_campaign_count(self, slug: str, key: str, by: int = 1) -> None:
        found = self._campaigns.get(slug)
        if found is None:
            raise LookupError("no such campaign")
        counts = {**found.counts, key: found.counts.get(key, 0) + by}
        self._campaigns[slug] = found.model_copy(update={"counts": counts})

    def get_launch_config(self) -> LaunchConfig:
        return self._launch.model_copy()

    def put_launch_config(self, config: LaunchConfig) -> None:
        self._launch = config.model_copy()
