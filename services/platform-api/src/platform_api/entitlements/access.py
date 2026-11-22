"""What a member may open. Pure: time is passed in, nothing is read or written."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Literal

from platform_api.entitlements.models import Access, Decision, Entitlement, Reason

TIERS: Mapping[str, tuple[str, ...]] = {
    "free": ("overview", "library", "account"),
    "paid": ("overview", "library", "account", "research", "guides"),
}

_RECENT = timedelta(days=30)


def is_live(e: Entitlement, now: datetime) -> bool:
    if e.status not in ("active", "grace"):
        return False
    if e.source == "grant":
        return e.valid_until is None or e.valid_until > now
    return True  # a source's date is a prompt to re-check, not an end


def label_for(
    e: Entitlement,
) -> Literal[
    "substack_subscription",
    "substack_status",
    "platform_subscription",
    "launch_grant",
    "owner_grant",
    "purchase",
]:
    if e.grant.startswith("status:"):
        return "substack_status"
    if e.source == "grant":
        return "launch_grant" if e.source_ref.startswith("campaign:") else "owner_grant"
    if e.source == "platform_stripe":
        return "platform_subscription"
    if e.source == "payhip":
        return "purchase"
    return "substack_subscription"


def _recently_ended_grant(e: Entitlement, now: datetime) -> tuple[bool, bool]:
    """(listed, date_has_passed) for a grant that is not live."""
    if e.source != "grant":
        return False, False
    passed = e.valid_until is not None and e.valid_until <= now
    end = e.valid_until if passed and e.valid_until is not None else e.updated_at
    return end > now - _RECENT, passed


def _reason(e: Entitlement, status: Literal["active", "grace", "expired", "revoked"]) -> Reason:
    substack = e.source in ("substack_stripe", "substack_roster")
    campaign = (
        e.source_ref.removeprefix("campaign:") if e.source_ref.startswith("campaign:") else None
    )
    return Reason(
        grant=e.grant,
        source=e.source,
        label=label_for(e),
        access_scope=e.access_scope,
        status=status,
        valid_until=e.valid_until,
        campaign=campaign if e.source == "grant" else None,
        plan_interval=e.plan_interval if substack else None,
    )


def access_from(entitlements: Sequence[Entitlement], now: datetime) -> Access:
    live = [e for e in entitlements if is_live(e, now)]
    tier: Literal["free", "paid"] = "paid" if any(e.grant == "tier:paid" for e in live) else "free"
    items = sorted({e.grant.removeprefix("item:") for e in live if e.grant.startswith("item:")})
    listed: list[tuple[Entitlement, Reason]] = [(e, _reason(e, e.status)) for e in live]
    for e in entitlements:
        if is_live(e, now):
            continue
        recent, passed = _recently_ended_grant(e, now)
        if recent:
            status = "expired" if e.status in ("active", "grace") and passed else e.status
            listed.append((e, _reason(e, status)))

    def newest_last(pair: tuple[Entitlement, Reason]) -> tuple[bool, datetime]:
        until = pair[0].valid_until
        return (until is None, until if until is not None else now)

    listed.sort(key=newest_last)
    return Access(
        tier=tier,
        sections=list(TIERS[tier]),
        items=items,
        reasons=[r for _, r in listed],
        computed_at=now,
    )


def decision_for(
    entitlements: Sequence[Entitlement],
    item_access: Literal["paid", "free_members", "purchase_only"],
    sku: str,
    now: datetime,
) -> Decision:
    if item_access == "free_members":
        return Decision(allowed=True, reason=None)
    access = access_from(entitlements, now)
    owns = sku in access.items
    if item_access == "paid":
        if access.tier == "paid" or owns:
            return Decision(allowed=True, reason=None)
        return Decision(allowed=False, reason="paid_required")
    if owns:
        return Decision(allowed=True, reason=None)
    return Decision(allowed=False, reason="purchase_required")
