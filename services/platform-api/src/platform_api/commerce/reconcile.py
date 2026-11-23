"""Read every Stripe subscription, map it, and hand the states to the entitlement engine.

Fail safe: a failed read applies nothing; a failure while applying may have applied
some writes (the run's `applying` count says so). And a run never stays `running`.
Logs name counts and exception classes only, never an address or an exception's text.
"""

import logging
from datetime import datetime
from typing import Literal, get_args

from platform_api.commerce.mapping import Skip, to_state
from platform_api.commerce.models import RequestedBy, RunKind, SyncRun
from platform_api.commerce.promotions import count_upgrades
from platform_api.commerce.runtime import get_runtime
from platform_api.entitlements import public as entitlements
from platform_api.entitlements.public import Entitlement, Guard, ReconcilePlan, SourceState
from platform_api.shared.events import new_event

logger = logging.getLogger(__name__)

_KIND: RunKind = "stripe_reconcile"


def would_do(plan: ReconcilePlan) -> dict[str, int]:
    """What a dry run reports. The plan cannot tell grants or tier changes: reported as 0."""
    by_kind = {k: sum(1 for a in plan.actions if a.kind == k) for k in ("create", "update", "end")}
    moved = sum(1 for a in plan.actions if a.kind == "move" and a.entitlement.status != "expired")
    return {
        "created": by_kind["create"],
        "updated": by_kind["update"],
        "ended": by_kind["end"],
        "moved": moved,
        "unchanged": plan.unchanged,
        "unseen": len(plan.unseen),
        "grants_created": 0,
        "tier_changes": 0,
    }


def created_records(plan: ReconcilePlan) -> list[Entitlement]:
    """The `substack_stripe` records a plan creates: its creates, and the record of a move
    created under its new contact."""
    return [
        a.entitlement
        for a in plan.actions
        if a.entitlement.source == "substack_stripe"
        and (a.kind == "create" or (a.kind == "move" and a.entitlement.status != "expired"))
    ]


class _NoReader(Exception):
    pass


def _work(
    dry_run: bool, run_id: str, now: datetime, counts: dict[str, int]
) -> Literal["passed", "blocked"]:
    """Fills `counts` in place, so a failure keeps what was counted so far."""
    rt = get_runtime()
    if rt.stripe is None:
        counts["no_reader"] = 1
        raise _NoReader
    subs = []
    for sub in rt.stripe.subscriptions():
        subs.append(sub)
        counts["seen"] += 1
    counts.update({word: 0 for word in get_args(Skip)})
    counts.update(states_active=0, states_grace=0, states_expired=0, no_period_end=0)
    states: list[SourceState] = []
    for sub in subs:
        state = to_state(sub, rt.settings, now)
        if isinstance(state, str):
            counts[state] += 1
        else:
            states.append(state)
            counts[f"states_{state.status}"] += 1
            if sub.status in ("trialing", "active") and sub.current_period_end is None:
                counts["no_period_end"] += 1
    existing = entitlements.existing_for(["substack_stripe"])
    plan = entitlements.plan_reconcile(existing, states, Guard(), now)
    counts.update(guard_ends=plan.ends, live_before=plan.live_before)
    if dry_run:
        counts.update(would_do(plan))
    else:
        counts["applying"] = 1  # from here a failure may have applied some writes
        report = entitlements.apply_plan(plan, run_id, now)
        counts.update(
            created=report.created,
            updated=report.updated,
            ended=report.ended,
            moved=report.moved,
            unchanged=report.unchanged,
            unseen=report.unseen,
            grants_created=report.grants_created,
            tier_changes=report.tier_changes,
        )
        if not plan.blocked:
            # Roster records are read for this count only: the plan sees its own source.
            prior = [*existing, *entitlements.existing_for(["substack_roster"])]
            counts["upgrades_counted"] = count_upgrades(created_records(plan), prior, now)
    return "blocked" if plan.blocked else "passed"


def stripe_reconcile(dry_run: bool, requested_by: RequestedBy, now: datetime) -> SyncRun:
    rt = get_runtime()
    run_id = rt.runs.start(_KIND, dry_run, requested_by, now)
    counts: dict[str, int] = {"seen": 0}
    try:
        guard = _work(dry_run, run_id, now, counts)
    except Exception as exc:
        logger.error(
            "alert=reconcile_failed run=%s dry_run=%s error=%s",
            run_id,
            dry_run,
            type(exc).__name__,
        )
        rt.runs.finish(run_id, "failed", None, counts, now)
    else:
        rt.runs.finish(run_id, "completed", guard, counts, now)
        if guard == "blocked":
            logger.error("alert=reconcile_guard_blocked run=%s dry_run=%s", run_id, dry_run)
        try:
            rt.bus.publish(
                new_event(
                    "commerce.reconcile.completed",
                    run_id,
                    {"run_id": run_id, "kind": _KIND, "dry_run": dry_run, "guard": guard, **counts},
                    now=now,
                )
            )
        except Exception as exc:
            logger.error(
                "reconcile_event_not_published run=%s error=%s", run_id, type(exc).__name__
            )
    run = rt.runs.get(run_id)
    if run is None:
        raise RuntimeError("run record missing")
    return run
