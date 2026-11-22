from datetime import datetime
from typing import Literal

from platform_api.entitlements.access import access_from, decision_for
from platform_api.entitlements.models import (
    Access,
    AuditEntry,
    ChannelsPatch,
    Contact,
    Decision,
    Entitlement,
    Reason,
    SourceState,
    entitlement_id,
    normalise_email,
)
from platform_api.entitlements.runtime import get_runtime
from platform_api.shared import clock

__all__ = [
    "Access",
    "Decision",
    "Reason",
    "access_for",
    "can_open",
    "AuditEntry",
    "ChannelsPatch",
    "Contact",
    "Entitlement",
    "SourceState",
    "contact_id_for",
    "entitlement_id",
    "upsert_contact",
]


def contact_id_for(email: str) -> str:
    """The only place an address becomes an id."""
    key = get_runtime().key
    return key.mac(normalise_email(email).encode()).hex()[:32]


def upsert_contact(email: str, channels: ChannelsPatch) -> str:
    runtime = get_runtime()
    contact_id = contact_id_for(email)
    now = clock.utcnow()
    existing = runtime.store.get_contact(contact_id)
    merged: dict[str, dict[str, object]] = (
        {k: dict(v) for k, v in existing.channels.items()} if existing else {}
    )
    for name, values in channels.model_dump(exclude_none=True).items():
        merged[name] = {**merged.get(name, {}), **values}
    if existing is None:
        contact = Contact(
            contact_id=contact_id,
            key_version=runtime.key.version,
            email=email.strip(),
            channels=merged,
            invite={"campaign": None, "state": "none"},
            created_at=now,
            updated_at=now,
        )
    else:
        contact = existing.model_copy(update={"channels": merged, "updated_at": now})
    runtime.store.put_contact(contact)
    return contact_id


def _held_by(uid: str) -> list[Entitlement]:
    store = get_runtime().store
    found = [
        *store.entitlements_for_member(uid),
        *store.entitlements_for_contacts(store.contact_ids_for_member(uid)),
    ]
    return list({e.entitlement_id: e for e in found}.values())


def access_for(uid: str, now: datetime) -> Access:
    return access_from(_held_by(uid), now)


def can_open(
    uid: str,
    sku: str,
    now: datetime,
    *,
    item_access: Literal["paid", "free_members", "purchase_only"] | None = None,
) -> Decision:
    # The Library port that names an item's access does not exist yet.
    if item_access is None:
        raise LookupError("the access of this item is not known")
    return decision_for(_held_by(uid), item_access, sku, now)
