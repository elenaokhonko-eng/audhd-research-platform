"""Read every Stripe subscription, map it, and hand the states to the entitlement engine.

Fail safe: a read that fails anywhere applies nothing, and a run never stays `running`.
Logs name counts and exception classes only, never an address or an exception's text.
"""

import logging
from datetime import datetime
from typing import Literal, get_args

from platform_api.commerce.mapping import Skip, to_state
from platform_api.commerce.models import RequestedBy, RunKind, SyncRun
from platform_api.commerce.runtime import get_runtime
from platform_api.entitlements import public as entitlements
from platform_api.entitlements.public import Guard, ReconcilePlan, SourceState
from platform_api.shared.events import new_event

logger = logging.getLogger(__name__)

_KIND: RunKind = "stripe_reconcile"


def _would_do(plan: ReconcilePlan) -> dict[str, int]:
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
    states: list[SourceState] = []
    for sub in subs:
        state = to_state(sub, rt.settings, now)
        if isinstance(state, str):
            counts[state] += 1
        else:
            states.append(state)
    plan = entitlements.plan_reconcile(
        entitlements.existing_for(["substack_stripe"]), states, Guard(), now
    )
    if dry_run:
        counts.update(_would_do(plan))
    else:
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
