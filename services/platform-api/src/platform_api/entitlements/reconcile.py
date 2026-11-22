"""What a source says now, turned into a plan of writes. Pure: nothing is read or written.

Fail safe (02 §4, Rule 3): a record no state mentions is left alone and listed in
`unseen`; a plan that would end, or move between contacts, more records than the
guard allows is `blocked` and carries no actions.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from platform_api.entitlements.access import is_live
from platform_api.entitlements.models import Entitlement, SourceState, entitlement_id

_BY_REFERENCE = ("substack_stripe", "platform_stripe")  # the reference is a subscription id
_PLANNED_BY = "run:"  # apply_plan stamps the run id and the time on every record it writes


class Guard(BaseModel):
    max_ends: int = 5
    max_fraction: float = 0.2


class Action(BaseModel):
    """One write. A `move` is two actions of kind `move`, in this order: the record
    created under its new contact (with `email` when that contact may need creating),
    then the old record ended under its old contact."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    kind: Literal["create", "update", "end", "move"]
    entitlement: Entitlement  # the record as it will be after the action
    email: str | None = Field(default=None, repr=False, exclude=True)
    evidence_source_ref: str


class ReconcilePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    actions: list[Action]
    unchanged: int
    unseen: list[str]  # entitlement ids
    blocked: bool
    ends: int
    live_before: int


class ReconcileReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    created: int
    updated: int
    ended: int
    moved: int
    unchanged: int
    unseen: int
    tier_changes: int
    grants_created: int
    blocked: bool


def _guarded(grant: str) -> bool:
    return grant.startswith(("tier:", "status:"))


def _refuse_duplicates(resolved: Sequence[tuple[str, SourceState]]) -> None:
    seen: set[tuple[str, ...]] = set()
    for contact_id, s in resolved:
        key = (
            (s.source, s.source_ref)
            if s.source in _BY_REFERENCE
            else (s.source, s.source_ref, contact_id)
        )
        if key in seen:
            where = "" if s.source in _BY_REFERENCE else f" for contact {contact_id}"
            raise ValueError(f"{s.source} reference {s.source_ref} appears twice{where}")
        seen.add(key)


def _from_state(
    contact_id: str, member_uid: str | None, s: SourceState, now: datetime
) -> Entitlement:
    return Entitlement(
        entitlement_id=entitlement_id(s.source, s.source_ref, contact_id, s.grant),
        contact_id=contact_id,
        member_uid=member_uid,
        grant=s.grant,
        source=s.source,
        source_ref=s.source_ref,
        access_scope=s.access_scope,
        plan_interval=s.plan_interval,
        valid_from=s.started_at,
        valid_until=s.valid_until,
        status=s.status,
        updated_at=now,
        updated_by=_PLANNED_BY,
    )


def _ended(record: Entitlement, s: SourceState, now: datetime) -> Entitlement:
    return record.model_copy(
        update={
            "status": "expired",
            "valid_until": s.provider_time,
            "updated_at": now,
            "updated_by": _PLANNED_BY,
        }
    )


def _live(e: Entitlement) -> bool:
    return e.status in ("active", "grace")


def _find(
    contact_id: str,
    s: SourceState,
    by_id: dict[str, Entitlement],
    by_ref: dict[tuple[str, str], list[Entitlement]],
) -> Entitlement | None:
    found = by_id.get(entitlement_id(s.source, s.source_ref, contact_id, s.grant))
    if s.source not in _BY_REFERENCE or (found is not None and _live(found)):
        return found
    sharing = by_ref.get((s.source, s.source_ref), [])
    live = sorted((e for e in sharing if _live(e)), key=lambda e: e.updated_at)
    if live:  # the subscription's live record wins over an ended one found by id
        return live[-1]
    if found is not None or not sharing:
        return found
    return sorted(sharing, key=lambda e: e.updated_at)[-1]


def plan(
    existing: Sequence[Entitlement],
    resolved: Sequence[tuple[str, SourceState]],
    guard: Guard,
    now: datetime,
) -> ReconcilePlan:
    _refuse_duplicates(resolved)
    by_id = {e.entitlement_id: e for e in existing}
    by_ref: dict[tuple[str, str], list[Entitlement]] = {}
    for e in existing:
        if e.source in _BY_REFERENCE:
            by_ref.setdefault((e.source, e.source_ref), []).append(e)

    actions: list[Action] = []
    seen: set[str] = set()
    unchanged = ends = moves_between_contacts = 0

    for contact_id, s in resolved:
        record = _find(contact_id, s, by_id, by_ref)
        if record is None:
            if s.status != "expired":
                actions.append(
                    Action(
                        kind="create",
                        entitlement=_from_state(contact_id, None, s, now),
                        email=s.email,
                        evidence_source_ref=s.source_ref,
                    )
                )
            continue

        seen.add(record.entitlement_id)
        if (
            record.source in _BY_REFERENCE
        ):  # ended records of the same subscription; never a live one
            sharing = by_ref[(record.source, record.source_ref)]
            seen.update(e.entitlement_id for e in sharing if not _live(e))
        if record.status == "revoked":
            unchanged += 1
            continue

        claimed = record.member_uid is not None
        home = record.contact_id if claimed else contact_id  # a claim sticks (Rule 4)
        email = s.email if home == contact_id else None
        live = _live(record)

        if s.status == "expired":
            if live:
                actions.append(
                    Action(
                        kind="end",
                        entitlement=_ended(record, s, now),
                        evidence_source_ref=s.source_ref,
                    )
                )
                ends += _guarded(record.grant)
            else:
                unchanged += 1
            continue

        if home != record.contact_id or s.grant != record.grant:
            fresh = _from_state(home, record.member_uid, s, now)
            if not live:
                actions.append(
                    Action(
                        kind="create",
                        entitlement=fresh,
                        email=email,
                        evidence_source_ref=s.source_ref,
                    )
                )
                continue
            actions.append(
                Action(
                    kind="move", entitlement=fresh, email=email, evidence_source_ref=s.source_ref
                )
            )
            actions.append(
                Action(
                    kind="move",
                    entitlement=_ended(record, s, now),
                    evidence_source_ref=s.source_ref,
                )
            )
            moves_between_contacts += home != record.contact_id
            continue

        target = record.model_copy(
            update={
                "status": s.status,
                "valid_from": s.started_at,
                "valid_until": s.valid_until,
                "plan_interval": s.plan_interval,
                "access_scope": s.access_scope,
            }
        )
        if target == record:
            unchanged += 1
            continue
        actions.append(
            Action(
                kind="update",
                entitlement=target.model_copy(
                    update={"updated_at": now, "updated_by": _PLANNED_BY}
                ),
                evidence_source_ref=s.source_ref,
            )
        )

    live_before = sum(1 for e in existing if _guarded(e.grant) and is_live(e, now))
    limit = max(guard.max_ends, guard.max_fraction * live_before)
    blocked = ends > limit or moves_between_contacts > limit
    return ReconcilePlan(
        actions=[] if blocked else actions,
        unchanged=unchanged,
        unseen=[e.entitlement_id for e in existing if e.entitlement_id not in seen],
        blocked=blocked,
        ends=ends,
        live_before=live_before,
    )
