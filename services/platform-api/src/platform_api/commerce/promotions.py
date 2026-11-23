"""Promotions shown in their window, the upgrade routes of a member, and upgrades counted.

A promotion is the owner's configuration: its words, its link and its dates come from her
private file, never from this code. A reader sees a `PromotionView`, which has no counts.
An upgrade is counted once per promotion and contact, and only from a record a real
reconcile created; the event carries ids only.
"""

import logging
from collections.abc import Sequence
from datetime import datetime

from platform_api.commerce.models import (
    Audience,
    Promotion,
    PromotionView,
    Route,
    UpgradeOptions,
)
from platform_api.commerce.runtime import get_runtime
from platform_api.entitlements import public as entitlements
from platform_api.entitlements.public import Entitlement
from platform_api.shared import clock
from platform_api.shared.events import new_event

logger = logging.getLogger(__name__)

_LIVE = ("active", "grace")
_PRIOR_SOURCES = ("substack_stripe", "substack_roster")


def _view(p: Promotion) -> PromotionView:
    return PromotionView(
        id=p.id,
        channel=p.channel,
        plan_interval=p.plan_interval,
        starts_at=p.starts_at,
        ends_at=p.ends_at,
        url=p.substack_offer_url if p.channel == "substack_offer" else None,
        display=dict(p.display),
    )


def _in_window(p: Promotion, when: datetime) -> bool:
    return p.starts_at <= when < p.ends_at


def active_promotions(audience: Audience, now: datetime) -> list[PromotionView]:
    """Nothing while `promotions_open` is off. A Substack offer without a link is never shown,
    and until platform checkout exists only Substack offers are."""
    if not entitlements.launch_config().promotions_open:
        return []
    shown = [
        p
        for p in get_runtime().promotions.list()
        if _in_window(p, now)
        and audience in p.audience
        and p.channel == "substack_offer"
        and p.substack_offer_url
    ]
    shown.sort(key=lambda p: (p.starts_at, p.id))
    return [_view(p) for p in shown]


def upgrade_options(uid: str, now: datetime) -> UpgradeOptions:
    access = entitlements.access_for(uid, now)
    if access.tier == "paid":
        return UpgradeOptions(routes=[], promotion=None)
    account_url = entitlements.launch_config().substack_account_url or None
    # Ruling 4: a reader who already pays Substack on a plan without the platform changes
    # the plan on Substack; whether an offer applies to a current payer is not known.
    if any(r.label == "substack_status" and r.status in _LIVE for r in access.reasons):
        route = Route(
            kind="substack_change_plan", available=account_url is not None, url=account_url
        )
        return UpgradeOptions(routes=[route], promotion=None)
    # One promotion gives both the words shown and the link followed.
    offer = next((v for v in active_promotions("free_members", now) if v.url), None)
    url = offer.url if offer is not None else account_url
    return UpgradeOptions(
        routes=[
            Route(kind="substack", available=url is not None, url=url),
            Route(kind="platform_only", available=False, url=None),
        ],
        promotion=offer,
    )


def put_promotions(promotions: list[Promotion], actor: str) -> int:
    """Write promotions from the owner's file. An id that exists keeps its counts; a new id
    starts with none. Promotions the file does not name stay. Each id once, or ValueError."""
    ids = [p.id for p in promotions]
    if len(set(ids)) != len(ids):
        raise ValueError("an id is named more than once")
    now = clock.utcnow()
    stamped = [
        p.model_copy(update={"counts": {}, "updated_at": now, "updated_by": actor})
        for p in promotions
    ]
    get_runtime().promotions.put_all(stamped)
    return len(stamped)


def _paid_before(contact_id: str, starts_at: datetime, existing: Sequence[Entitlement]) -> bool:
    """A Substack record of the contact that had started by `starts_at` and is live by its
    status as read. A record without a start is taken as started: never count on a guess."""
    return any(
        e.contact_id == contact_id
        and e.source in _PRIOR_SOURCES
        and e.status in _LIVE
        and (e.valid_from is None or e.valid_from <= starts_at)
        for e in existing
    )


def count_upgrades(
    created: Sequence[Entitlement], existing: Sequence[Entitlement], now: datetime
) -> int:
    """Count the `substack_stripe` records a real reconcile created inside a promotion's
    window, once per promotion and contact, for a contact that was not paying already."""
    rt = get_runtime()
    # A created record of a subscription already seen continues it (a move to another
    # address): it was counted, if at all, when it was first created.
    seen = {e.source_ref for e in existing if e.source == "substack_stripe"}
    counted = 0
    for p in rt.promotions.list():
        if p.channel != "substack_offer":
            continue  # until platform checkout exists, only a Substack offer is counted
        for record in created:
            if record.source != "substack_stripe" or record.valid_from is None:
                continue
            if record.source_ref in seen:
                continue
            if not _in_window(p, record.valid_from):
                continue
            if _paid_before(record.contact_id, p.starts_at, existing):
                continue
            if not rt.promotions.count_once(p.id, record.contact_id):
                continue
            counted += 1
            try:
                rt.bus.publish(
                    new_event(
                        "commerce.promotion.upgrade_counted",
                        record.contact_id,
                        {
                            "promotion_id": p.id,
                            "contact_id": record.contact_id,
                            "channel": p.channel,
                            "source_ref": record.source_ref,
                        },
                        now=now,
                    )
                )
            except Exception as exc:
                logger.error(
                    "upgrade_event_not_published promotion=%s error=%s", p.id, type(exc).__name__
                )
    return counted
