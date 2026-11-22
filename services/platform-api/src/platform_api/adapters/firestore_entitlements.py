"""The entitlements store on Firestore: collections of 09 section 2 and contracts section 4.

`contacts/{contact_id}`, `entitlements/{entitlement_id}`, `audit_log/{auto}`,
`campaigns/{slug}` and `config/launch`. Documents are the models' fields as they dump
(`Campaign` by alias, so its `copy` is stored as `copy`). Every change that must not be
lost to a concurrent writer runs in a transaction.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import firestore
from google.cloud.firestore import FieldFilter, Increment
from google.cloud.firestore_v1.field_path import FieldPath

from platform_api.adapters import in_transaction
from platform_api.entitlements.models import (
    AuditEntry,
    Campaign,
    Contact,
    Entitlement,
    LaunchConfig,
    Source,
)
from platform_api.entitlements.store import ContactChange, check_write

_IN_LIMIT = 30  # the most values Firestore takes in one `in` filter


def _data(snapshot: Any) -> dict[str, Any] | None:
    if not snapshot.exists:
        return None
    found: dict[str, Any] | None = snapshot.to_dict()
    return found


class FirestoreEntitlementStore:
    def __init__(self, client: firestore.Client) -> None:
        self._client = client
        self._contacts = client.collection("contacts")
        self._entitlements = client.collection("entitlements")
        self._audit = client.collection("audit_log")
        self._campaigns = client.collection("campaigns")
        self._launch = client.collection("config").document("launch")

    # contacts

    def get_contact(self, contact_id: str) -> Contact | None:
        found = _data(self._contacts.document(contact_id).get())
        return Contact.model_validate(found) if found is not None else None

    def put_contact(self, contact: Contact) -> None:
        self._contacts.document(contact.contact_id).set(contact.model_dump())

    def merge_contact(self, contact_id: str, change: ContactChange) -> Contact | None:
        ref = self._contacts.document(contact_id)

        def work(transaction: firestore.Transaction) -> Contact | None:
            found = _data(ref.get(transaction=transaction))
            held = Contact.model_validate(found) if found is not None else None
            changed = change(held)
            if changed is None:
                return held
            if changed.contact_id != contact_id:
                raise ValueError("a change may not move a contact to another id")
            transaction.set(ref, changed.model_dump())
            return changed

        return in_transaction(self._client, work)

    def contact_ids_for_member(self, uid: str) -> list[str]:
        query = self._contacts.where(filter=FieldFilter("channels.platform.member_uid", "==", uid))
        return [snapshot.id for snapshot in query.stream()]

    # entitlements

    def _entitlements_where(self, field: str, op: str, value: object) -> list[Entitlement]:
        query = self._entitlements.where(filter=FieldFilter(field, op, value))
        return [Entitlement.model_validate(s.to_dict()) for s in query.stream()]

    def entitlements_for_contacts(self, contact_ids: Sequence[str]) -> list[Entitlement]:
        wanted = list(dict.fromkeys(contact_ids))
        found: list[Entitlement] = []
        for i in range(0, len(wanted), _IN_LIMIT):
            found += self._entitlements_where("contact_id", "in", wanted[i : i + _IN_LIMIT])
        return found

    def entitlements_for_member(self, uid: str) -> list[Entitlement]:
        return self._entitlements_where("member_uid", "==", uid)

    def entitlements_by_source(self, source: Source) -> list[Entitlement]:
        return self._entitlements_where("source", "==", source)

    def get_entitlement(self, entitlement_id: str) -> Entitlement | None:
        found = _data(self._entitlements.document(entitlement_id).get())
        return Entitlement.model_validate(found) if found is not None else None

    def write(
        self, contact_id: str, entitlements: Sequence[Entitlement], audit: Sequence[AuditEntry]
    ) -> None:
        check_write(contact_id, entitlements)  # before anything is written
        if not entitlements and not audit:
            return

        def work(transaction: firestore.Transaction) -> None:
            for e in entitlements:
                transaction.set(self._entitlements.document(e.entitlement_id), e.model_dump())
            self._stage_audit(transaction, audit)

        in_transaction(self._client, work)

    def create_if_absent(self, entitlement: Entitlement, audit: AuditEntry) -> bool:
        ref = self._entitlements.document(entitlement.entitlement_id)

        def work(transaction: firestore.Transaction) -> bool:
            if ref.get(transaction=transaction).exists:
                return False
            transaction.set(ref, entitlement.model_dump())
            self._stage_audit(transaction, [audit])
            return True

        return in_transaction(self._client, work)

    # audit

    def _stage_audit(
        self, transaction: firestore.Transaction, entries: Iterable[AuditEntry]
    ) -> None:
        for entry in entries:
            transaction.set(self._audit.document(), entry.model_dump())

    def audit_for(self, subject: str) -> list[AuditEntry]:
        query = self._audit.where(filter=FieldFilter("subject", "==", subject))
        found = [AuditEntry.model_validate(s.to_dict()) for s in query.stream()]
        return sorted(found, key=lambda a: a.at)

    # campaigns

    def get_campaign(self, slug: str) -> Campaign | None:
        found = _data(self._campaigns.document(slug).get())
        return Campaign.model_validate(found) if found is not None else None

    def list_campaigns(self) -> list[Campaign]:
        return [Campaign.model_validate(s.to_dict()) for s in self._campaigns.stream()]

    def put_campaigns(self, campaigns: Sequence[Campaign]) -> None:
        refs = [(self._campaigns.document(c.slug), c) for c in campaigns]

        def work(transaction: firestore.Transaction) -> None:
            stored = [ref.get(transaction=transaction).exists for ref, _ in refs]  # reads first
            for (ref, campaign), exists in zip(refs, stored, strict=True):
                data = campaign.model_dump(by_alias=True)
                if exists:
                    del data["counts"]  # a stored slug keeps its counts
                    transaction.update(ref, data)
                else:
                    transaction.set(ref, data)

        if refs:
            in_transaction(self._client, work)

    def add_to_campaign_count(self, slug: str, key: str, by: int = 1) -> None:
        path = FieldPath("counts", key).to_api_repr()
        try:
            self._campaigns.document(slug).update({path: Increment(by)})
        except NotFound:
            raise LookupError("no such campaign") from None

    # config/launch

    def get_launch_config(self) -> LaunchConfig:
        found = _data(self._launch.get())
        return LaunchConfig.model_validate(found) if found is not None else LaunchConfig()

    def put_launch_config(self, config: LaunchConfig) -> None:
        self._launch.set(config.model_dump())
