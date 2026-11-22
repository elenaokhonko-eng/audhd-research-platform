from platform_api.entitlements.models import (
    AuditEntry,
    ChannelsPatch,
    Contact,
    Entitlement,
    SourceState,
    entitlement_id,
    normalise_email,
)
from platform_api.entitlements.runtime import get_runtime
from platform_api.shared import clock

__all__ = [
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
