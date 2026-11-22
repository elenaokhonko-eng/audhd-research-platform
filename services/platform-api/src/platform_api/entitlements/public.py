import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from platform_api.entitlements import reconcile
from platform_api.entitlements.access import _reason, access_from, decision_for, is_live
from platform_api.entitlements.campaigns import campaign_state, grants_from
from platform_api.entitlements.models import (
    _SLUG,
    Access,
    AuditEntry,
    Campaign,
    ChannelsPatch,
    Contact,
    ContactView,
    Decision,
    Entitlement,
    GrantPolicy,
    GrantSpec,
    LaunchConfig,
    Reason,
    ReasonEntry,
    Source,
    SourceState,
    entitlement_id,
    normalise_email,
)
from platform_api.entitlements.reconcile import Action, Guard, ReconcilePlan, ReconcileReport
from platform_api.entitlements.runtime import get_runtime
from platform_api.shared import clock
from platform_api.shared.events import contains_email, new_event

__all__ = [
    "Access",
    "Decision",
    "Reason",
    "access_for",
    "apply_plan",
    "existing_for",
    "Source",
    "Guard",
    "plan_reconcile",
    "ReconcilePlan",
    "ReconcileReport",
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
    "Campaign",
    "ContactView",
    "GrantPolicy",
    "GrantSpec",
    "LaunchConfig",
    "ReasonEntry",
    "apply_grant_policies",
    "audit_for",
    "campaign_by_slug",
    "campaign_state",
    "contact_view",
    "grants_due",
    "launch_config",
    "list_campaigns",
    "put_campaigns",
    "record_arrival",
    "update_launch_config",
    "write_audit",
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
    contact_id: str,
    uid: str | None,
    before: str | None,
    now: datetime,
    *,
    run_id: str = "owner",
    reason: str = "owner_action",
) -> bool:
    """Publish `membership.tier.changed` when the member's tier differs from `before`."""
    if uid is None or before is None:
        return False
    after = access_for(uid, now).tier
    if after == before:
        return False
    get_runtime().bus.publish(
        new_event(
            "membership.tier.changed",
            contact_id,
            {
                "member_uid": uid,
                "contact_id": contact_id,
                "from": before,
                "to": after,
                "run_id": run_id,
                "reason": reason,
            },
            now=now,
        )
    )
    return True


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


def launch_config() -> LaunchConfig:
    return get_runtime().store.get_launch_config()


def update_launch_config(patch: dict[str, object], actor: str) -> LaunchConfig:
    """Change some of the owner's switches. Unknown keys are refused; the change is audited."""
    unknown = sorted(set(patch) - set(LaunchConfig.model_fields))
    if unknown:
        raise ValueError("unknown launch settings: " + ", ".join(unknown))
    store = get_runtime().store
    config = LaunchConfig.model_validate({**store.get_launch_config().model_dump(), **patch})
    store.put_launch_config(config)
    write_audit(
        AuditEntry(
            at=clock.utcnow(),
            actor=actor,
            action="launch.switched",
            subject="config/launch",
            reason=None,
            evidence={"changed": ",".join(sorted(patch))},
        )
    )
    return config


def write_audit(entry: AuditEntry) -> None:
    """An audit entry that goes with no record: an owner's change of configuration."""
    get_runtime().store.write("", [], [entry])


def audit_for(subject: str) -> list[AuditEntry]:
    return get_runtime().store.audit_for(subject)


def list_campaigns() -> list[Campaign]:
    return get_runtime().store.list_campaigns()


def put_campaigns(campaigns: list[Campaign], actor: str) -> int:
    """Write campaigns from the owner's file. A slug that exists keeps its counts.

    Stored campaigns the file does not name stay. Refused with ValueError, before anything is
    written: a slug named twice, or anything but exactly one default once the file is merged
    by slug.
    """
    slugs = [c.slug for c in campaigns]
    if len(set(slugs)) != len(slugs):
        raise ValueError("a slug is named more than once")
    store = get_runtime().store
    merged = {c.slug: c for c in store.list_campaigns()} | {c.slug: c for c in campaigns}
    if sum(c.is_default for c in merged.values()) != 1:
        raise ValueError("exactly one campaign must be the default")
    now = clock.utcnow()
    kept = []
    for c in campaigns:
        held = store.get_campaign(c.slug)
        kept.append(c.model_copy(update={"counts": dict(held.counts)}) if held else c)
    store.put_campaigns(kept)
    for c in kept:
        write_audit(
            AuditEntry(
                at=now,
                actor=actor,
                action="campaign.written",
                subject=f"campaigns/{c.slug}",
                reason=None,
                evidence={"campaign": c.slug},
            )
        )
    return len(kept)


def campaign_by_slug(slug: str | None, now: datetime) -> Campaign:
    """The named campaign; an unknown slug, None or "default" give the default campaign."""
    store = get_runtime().store
    found = None
    if slug is not None and slug != "default" and _SLUG.fullmatch(slug):  # never look up junk
        found = store.get_campaign(slug)
    if found is not None:
        return found
    for c in store.list_campaigns():
        if c.is_default:
            return c
    raise LookupError("no default campaign is stored")


def grants_due(
    entitlements: list[Entitlement], campaigns: list[Campaign], now: datetime
) -> list[GrantSpec]:
    return grants_from(entitlements, campaigns, launch_config(), now)


def apply_grant_policies(contact_id: str, now: datetime) -> list[str]:
    """Create the launch grants due to a contact that has a member. Idempotent.

    Publishes `membership.entitlement.granted` for each grant it creates, and no tier
    change: `apply_plan` and sign-in compare the tier themselves.
    """
    runtime = get_runtime()
    store = runtime.store
    contact = store.get_contact(contact_id)
    uid = _platform_uid(contact) if contact else None
    if uid is None:
        return []
    held = store.entitlements_for_contacts([contact_id])
    created: list[str] = []
    for spec in grants_due(held, store.list_campaigns(), now):
        if spec.contact_id != contact_id:
            continue
        source_ref = f"campaign:{spec.campaign}"
        actor = f"policy:{spec.campaign}"
        record = Entitlement(
            entitlement_id=entitlement_id("grant", source_ref, contact_id, spec.grant),
            contact_id=contact_id,
            member_uid=uid,
            grant=spec.grant,
            source="grant",
            source_ref=source_ref,
            access_scope="platform_only",
            plan_interval=None,
            valid_from=now,
            valid_until=spec.valid_until,
            status="active",
            updated_at=now,
            updated_by=actor,
        )
        audit = AuditEntry(
            at=now,
            actor=actor,
            action="entitlement.granted",
            subject=record.entitlement_id,
            reason="launch_grant",
            evidence={"entitlement_id": spec.evidence_entitlement_id, "campaign": spec.campaign},
        )
        if not store.create_if_absent(record, audit):
            continue  # created meanwhile by another evaluation: counted there
        store.add_to_campaign_count(spec.campaign, "grants_created")
        runtime.bus.publish(
            new_event(
                "membership.entitlement.granted",
                contact_id,
                {
                    "contact_id": contact_id,
                    "entitlement_id": record.entitlement_id,
                    "grant": spec.grant,
                    "source": "grant",
                    "source_ref": source_ref,
                    "access_scope": "platform_only",
                },
                now=now,
            )
        )
        created.append(record.entitlement_id)
    return created


def record_arrival(uid: str, campaign: Campaign, recognition: str) -> None:
    """A member's first sign-in through a campaign: invite, counts and one event."""
    runtime = get_runtime()
    store = runtime.store
    contact_ids = store.contact_ids_for_member(uid)
    if not contact_ids:
        raise LookupError("no contact for this member")
    contact_id = contact_ids[0]
    contact = store.get_contact(contact_id)
    if contact is None:
        raise LookupError("no contact for this member")
    now = clock.utcnow()
    store.put_contact(
        contact.model_copy(
            update={"invite": {"campaign": campaign.slug, "state": "accepted"}, "updated_at": now}
        )
    )
    store.add_to_campaign_count(campaign.slug, "arrivals")
    if recognition == "paid":
        store.add_to_campaign_count(campaign.slug, "recognised_paid")
    runtime.bus.publish(
        new_event(
            "membership.campaign.joined",
            contact_id,
            {
                "member_uid": uid,
                "contact_id": contact_id,
                "campaign": campaign.slug,
                "recognition": recognition,
            },
            now=now,
        )
    )


def contact_view(contact_id: str, now: datetime) -> ContactView | None:
    """The owner's view of one contact: channels, records with reasons, their audit. No address."""
    store = get_runtime().store
    contact = store.get_contact(contact_id)
    if contact is None:
        return None
    held = store.entitlements_for_contacts([contact_id])
    reasons = []
    audit: list[AuditEntry] = []
    for e in held:
        ended = e.status in ("active", "grace") and not is_live(e, now)
        reasons.append(
            ReasonEntry(
                entitlement_id=e.entitlement_id, reason=_reason(e, "expired" if ended else e.status)
            )
        )
        audit.extend(store.audit_for(e.entitlement_id))
    audit.sort(key=lambda a: a.at)
    return ContactView(
        contact_id=contact_id,
        channels=contact.channels,
        has_member=_platform_uid(contact) is not None,
        reasons=reasons,
        audit=audit,
    )


def existing_for(sources: Sequence[Source]) -> list[Entitlement]:
    """Every record of the named sources, whatever its status: the `existing` of a run."""
    store = get_runtime().store
    found = [e for source in dict.fromkeys(sources) for e in store.entitlements_by_source(source)]
    return list({e.entitlement_id: e for e in found}.values())


def plan_reconcile(
    existing: Sequence[Entitlement], states: Sequence[SourceState], guard: Guard, now: datetime
) -> ReconcilePlan:
    """Resolve each address to its contact id, then plan without reading or writing."""
    return reconcile.plan(existing, [(contact_id_for(s.email), s) for s in states], guard, now)


def _audit_entry(action: Action, run_id: str, now: datetime, partner: str | None) -> AuditEntry:
    evidence = {"run_id": run_id, "source_ref": action.evidence_source_ref}
    if partner is not None:
        key = "moved_to" if action.entitlement.status == "expired" else "moved_from"
        evidence[key] = partner
    verb = {"create": "created", "update": "updated", "end": "ended", "move": "moved"}
    return AuditEntry(
        at=now,
        actor=f"run:{run_id}",
        action=f"entitlement.{verb[action.kind]}",
        subject=action.entitlement.entitlement_id,
        reason="reconcile",
        evidence=evidence,
    )


def apply_plan(plan: ReconcilePlan, run_id: str, now: datetime) -> ReconcileReport:
    """Write a plan: one write per contact, a moved record created before its old one ends.

    A member's tier is compared before the first write and after the last write and the
    grant policies, so a member gets at most one `membership.tier.changed` per run.
    """
    counts = {
        kind: sum(1 for a in plan.actions if a.kind == kind) for kind in ("create", "update", "end")
    }
    moved = sum(1 for a in plan.actions if a.kind == "move" and a.entitlement.status != "expired")
    report = ReconcileReport(
        run_id=run_id,
        created=0,
        updated=0,
        ended=0,
        moved=0,
        unchanged=plan.unchanged,
        unseen=len(plan.unseen),
        tier_changes=0,
        grants_created=0,
        blocked=plan.blocked,
    )
    if plan.blocked or not plan.actions:
        return report

    store = get_runtime().store
    touched = list(dict.fromkeys(a.entitlement.contact_id for a in plan.actions))
    before: dict[str, tuple[str, str]] = {}  # member uid -> (contact id, tier before)
    for contact_id in touched:
        contact = store.get_contact(contact_id)
        uids = [_platform_uid(contact) if contact else None]
        uids += [
            a.entitlement.member_uid for a in plan.actions if a.entitlement.contact_id == contact_id
        ]
        for uid in uids:
            if uid is not None and uid not in before:
                before[uid] = (contact_id, access_for(uid, now).tier)

    partner: dict[int, str] = {}
    for i, a in enumerate(plan.actions):
        if a.kind == "move" and a.entitlement.status != "expired":
            partner[i] = plan.actions[i + 1].entitlement.entitlement_id
            partner[i + 1] = a.entitlement.entitlement_id

    first: dict[str, list[tuple[Entitlement, AuditEntry]]] = {}
    then: dict[str, list[tuple[Entitlement, AuditEntry]]] = {}
    for i, a in enumerate(plan.actions):
        record = a.entitlement
        if a.email is not None:
            upsert_contact(a.email, ChannelsPatch())
        creates = a.kind == "create" or (a.kind == "move" and record.status != "expired")
        if creates and record.member_uid is None:
            contact = store.get_contact(record.contact_id)
            uid = _platform_uid(contact) if contact else None
            if uid is not None:
                record = record.model_copy(update={"member_uid": uid})
        record = record.model_copy(update={"updated_at": now, "updated_by": f"run:{run_id}"})
        ends_a_move = a.kind == "move" and record.status == "expired"
        (then if ends_a_move else first).setdefault(record.contact_id, []).append(
            (record, _audit_entry(a, run_id, now, partner.get(i)))
        )
    for writes in (first, then):  # never a moment with neither record of a move
        for contact_id, pairs in writes.items():
            store.write(contact_id, [e for e, _ in pairs], [entry for _, entry in pairs])

    grants_created = 0
    for contact_id in touched:
        contact = store.get_contact(contact_id)
        uid = _platform_uid(contact) if contact else None
        if uid is not None:
            grants_created += len(apply_grant_policies(contact_id, now))
    tier_changes = sum(
        _announce_tier_change(contact_id, uid, tier, now, run_id=run_id, reason="reconcile")
        for uid, (contact_id, tier) in before.items()
    )
    return report.model_copy(
        update={
            "created": counts["create"],
            "updated": counts["update"],
            "ended": counts["end"],
            "moved": moved,
            "tier_changes": tier_changes,
            "grants_created": grants_created,
        }
    )
