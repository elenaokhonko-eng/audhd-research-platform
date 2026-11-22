import hashlib
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
from platform_api.shared.events import contains_email, new_event

__all__ = [
    "Access",
    "Decision",
    "Reason",
    "access_for",
    "can_open",
    "claim_for_member",
    "grant",
    "revoke",
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
        held = merged.get(name, {})
        combined = {**held, **values}
        if name == "platform" and held.get("member_uid") is not None:
            combined["member_uid"] = held["member_uid"]  # a claim is never overwritten
        merged[name] = combined
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
        *(
            e
            for e in store.entitlements_for_contacts(store.contact_ids_for_member(uid))
            if e.member_uid is None or e.member_uid == uid
        ),
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


def _check_reason(reason: str) -> None:
    if not reason.strip():
        raise ValueError("a reason is required")
    if contains_email(reason):
        raise ValueError("a reason must not contain an email address")


def _member_tier(contact: Contact | None, now: datetime) -> tuple[str | None, str | None]:
    uid = _platform_uid(contact) if contact else None
    return (uid, access_for(uid, now).tier if uid else None)


def _announce_tier_change(
    contact_id: str, uid: str | None, before: str | None, now: datetime
) -> None:
    if uid is None or before is None:
        return
    after = access_for(uid, now).tier
    if after == before:
        return
    get_runtime().bus.publish(
        new_event(
            "membership.tier.changed",
            contact_id,
            {
                "member_uid": uid,
                "contact_id": contact_id,
                "from": before,
                "to": after,
                "run_id": "owner",
                "reason": "owner_action",
            },
            now=now,
        )
    )


def _platform_uid(contact: Contact) -> str | None:
    uid = contact.channels.get("platform", {}).get("member_uid")
    return uid if isinstance(uid, str) else None


def claim_for_member(uid: str, contact_id: str) -> list[str]:
    """Attach what is waiting under a contact to the member who proved they own it."""
    store = get_runtime().store
    contact = store.get_contact(contact_id)
    if contact is None:
        return []
    owner = _platform_uid(contact)
    if owner is not None and owner != uid:
        return []
    now = clock.utcnow()
    waiting = [e for e in store.entitlements_for_contacts([contact_id]) if e.member_uid is None]
    claimed = [
        e.model_copy(update={"member_uid": uid, "updated_at": now, "updated_by": f"member:{uid}"})
        for e in waiting
    ]
    audit = [
        AuditEntry(
            at=now,
            actor=f"member:{uid}",
            action="entitlement.claimed",
            subject=e.entitlement_id,
            reason=None,
            evidence={"contact_id": contact_id},
        )
        for e in claimed
    ]
    if owner is None:
        platform = {**contact.channels.get("platform", {}), "member_uid": uid}
        platform.setdefault("registered_at", now.isoformat())
        store.put_contact(
            contact.model_copy(
                update={"channels": {**contact.channels, "platform": platform}, "updated_at": now}
            )
        )
    if claimed:
        store.write(contact_id, claimed, audit)
    return [e.entitlement_id for e in claimed]


def grant(
    contact_id: str,
    grant: str,
    valid_until: datetime | None,
    reason: str,
    actor: str,
    now: datetime,
) -> str:
    """An owner gives access by hand. Always with a reason, always audited."""
    _check_reason(reason)
    if grant != "tier:paid" and not (grant.startswith("item:") and grant[5:].strip()):
        raise ValueError("a grant is tier:paid or item:<sku>")
    if valid_until is not None and valid_until <= now:
        raise ValueError("a grant must end after it starts")
    runtime = get_runtime()
    contact = runtime.store.get_contact(contact_id)
    if contact is None:
        raise LookupError("no such contact")
    uid, tier_before = _member_tier(contact, now)
    source_ref = "owner:" + hashlib.sha256((reason + now.isoformat()).encode()).hexdigest()[:12]
    entitlement = Entitlement(
        entitlement_id=entitlement_id("grant", source_ref, contact_id, grant),
        contact_id=contact_id,
        member_uid=_platform_uid(contact),
        grant=grant,
        source="grant",
        source_ref=source_ref,
        access_scope="platform_only",
        plan_interval=None,
        valid_from=now,
        valid_until=valid_until,
        status="active",
        updated_at=now,
        updated_by=actor,
    )
    audit = AuditEntry(
        at=now,
        actor=actor,
        action="entitlement.granted",
        subject=entitlement.entitlement_id,
        reason=reason,
        evidence={"contact_id": contact_id},
    )
    if not runtime.store.create_if_absent(entitlement, audit):
        raise ValueError("grant already exists")
    runtime.bus.publish(
        new_event(
            "membership.entitlement.granted",
            contact_id,
            {
                "contact_id": contact_id,
                "entitlement_id": entitlement.entitlement_id,
                "grant": grant,
                "source": "grant",
                "source_ref": source_ref,
                "access_scope": "platform_only",
            },
            now=now,
        )
    )
    _announce_tier_change(contact_id, uid, tier_before, now)
    return entitlement.entitlement_id


def revoke(entitlement_id: str, reason: str, actor: str, now: datetime) -> None:
    """Only a grant can be revoked: a source ends only its own records."""
    runtime = get_runtime()
    found = runtime.store.get_entitlement(entitlement_id)
    if found is None:
        raise LookupError("no such entitlement")
    if found.source != "grant":
        raise ValueError("only a grant can be revoked by hand")
    _check_reason(reason)
    if found.status == "revoked":
        return
    uid, tier_before = _member_tier(runtime.store.get_contact(found.contact_id), now)
    revoked = found.model_copy(update={"status": "revoked", "updated_at": now, "updated_by": actor})
    audit = AuditEntry(
        at=now,
        actor=actor,
        action="entitlement.revoked",
        subject=entitlement_id,
        reason=reason,
        evidence={"contact_id": found.contact_id},
    )
    runtime.store.write(found.contact_id, [revoked], [audit])
    runtime.bus.publish(
        new_event(
            "membership.entitlement.ended",
            found.contact_id,
            {
                "entitlement_id": entitlement_id,
                "contact_id": found.contact_id,
                "status": "revoked",
                "reason": "revoked",
            },
            now=now,
        )
    )
    _announce_tier_change(found.contact_id, uid, tier_before, now)
