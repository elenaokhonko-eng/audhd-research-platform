"""Campaigns and the launch grant policy (design 5.4). Pure: time is passed in."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from platform_api.entitlements.access import is_live
from platform_api.entitlements.models import (
    Campaign,
    Entitlement,
    GrantPolicy,
    GrantSpec,
    LaunchConfig,
    entitlement_id,
)
from platform_api.shared.clock import add_months


def campaign_state(
    campaign: Campaign, config: LaunchConfig, now: datetime
) -> Literal["scheduled", "open", "closed"]:
    if not config.join_open:
        return "closed"
    if campaign.opens_at is not None and now < campaign.opens_at:
        return "scheduled"
    if campaign.closes_at is not None and now >= campaign.closes_at:
        return "closed"
    return "open"


def _qualifies(e: Entitlement, policy: GrantPolicy, now: datetime) -> bool:
    if not is_live(e, now) or e.source not in policy.requires_live_source:
        return False
    if policy.paid_since_before is not None and (
        e.valid_from is None or e.valid_from >= policy.paid_since_before
    ):
        return False
    return policy.plan_intervals is None or e.plan_interval in policy.plan_intervals


def _valid_until(policy: GrantPolicy, now: datetime) -> datetime | None:
    if policy.starts == "at_claim":
        return add_months(now, policy.months) if policy.months is not None else None
    return policy.fixed_until


def grants_from(
    entitlements: Sequence[Entitlement],
    campaigns: Sequence[Campaign],
    config: LaunchConfig,
    now: datetime,
) -> list[GrantSpec]:
    """The launch grants that are due: one per open campaign with a policy and per contact."""
    existing = {e.entitlement_id for e in entitlements}  # whatever its status
    specs: list[GrantSpec] = []
    for c in campaigns:
        policy = c.grant
        if policy is None or campaign_state(c, config, now) != "open":
            continue
        until = _valid_until(policy, now)
        if until is None or until <= now:  # a grant that would end before it starts
            continue
        seen: set[str] = set()
        for e in entitlements:
            if e.contact_id in seen or not _qualifies(e, policy, now):
                continue
            grant_id = entitlement_id("grant", f"campaign:{c.slug}", e.contact_id, policy.grant)
            if grant_id in existing:
                continue
            seen.add(e.contact_id)
            specs.append(
                GrantSpec(
                    campaign=c.slug,
                    contact_id=e.contact_id,
                    grant=policy.grant,
                    valid_until=until,
                    evidence_entitlement_id=e.entitlement_id,
                )
            )
    return specs
