"""Recognise the readers Stripe cannot see, from Substack's subscriber export file.

Only rows without a plan interval (complimentary, gift, billed by Apple) whose reader has
no live `substack_stripe` record become `substack_roster` records, as `status:substack_paid`.
A row with a plan interval is a card payer: Stripe is the authority for those, so such a
row is counted and never granted. No state is ever `expired`, so an import ends nothing;
people the file leaves out are unseen.

Fail safe: the import refuses unless the latest real Stripe reconcile completed with its
guard passed less than 24 hours ago; a cut-off file, or one with a plan the Desk cannot
read, applies nothing; a run never stays `running`. Logs carry counts, column names and
the Desk's redacted values only, never an address, a row, or an exception's text.
"""

import logging
from datetime import datetime, timedelta
from typing import Literal

from substack_desk.adapters.export_file import ExportHeaderError, FileDirectory

from platform_api.commerce.models import RunKind, SyncRun
from platform_api.commerce.reconcile import would_do
from platform_api.commerce.runtime import get_runtime
from platform_api.entitlements import public as entitlements
from platform_api.entitlements.public import ChannelsPatch, Guard, SourceState
from platform_api.shared.events import new_event

logger = logging.getLogger(__name__)

_KIND: RunKind = "roster_import"
_RECONCILE_FRESH_FOR = timedelta(hours=24)


class _Stopped(Exception):
    """The run stopped for a reason already counted and logged."""


def _recent_good_reconcile(now: datetime) -> bool:
    """The latest real reconcile, whatever its state, completed and passed in the last 24 hours."""
    run = get_runtime().runs.latest("stripe_reconcile", real_only=True)
    return (
        run is not None
        and run.state == "completed"
        and run.guard == "passed"
        and run.finished_at is not None
        and now - run.finished_at < _RECONCILE_FRESH_FOR
    )


def _work(
    dry_run: bool, run_id: str, now: datetime, counts: dict[str, int]
) -> Literal["passed", "blocked"]:
    """Fills `counts` in place, so a failure keeps what was counted so far."""
    rt = get_runtime()
    if not _recent_good_reconcile(now):
        counts["refused_no_recent_reconcile"] = 1
        logger.error("alert=roster_refused run=%s dry_run=%s", run_id, dry_run)
        raise _Stopped
    found = rt.inbox.newest() if rt.inbox is not None else None
    if found is None:
        counts["no_file"] = 1
        logger.error("roster_no_file run=%s dry_run=%s", run_id, dry_run)
        raise _Stopped

    directory = FileDirectory(found.data, found.updated_at)
    missing: tuple[str, ...] | None = None
    try:
        listing = directory.list_paid()
    except ExportHeaderError as exc:
        missing = exc.missing  # column names from the Desk's own list, never a cell
    if missing is not None:  # logged outside the except block: no chained file content
        counts["bad_header"] = 1
        if missing:
            logger.error(
                "roster_bad_header run=%s dry_run=%s missing=%s",
                run_id,
                dry_run,
                ",".join(missing),
            )
        else:  # the Desk names no column only when the bytes are not UTF-8 text
            logger.error("roster_bad_header run=%s dry_run=%s reason=not_utf8", run_id, dry_run)
        raise _Stopped
    report = directory.report
    counts.update(
        rows=report.rows_read,
        rejected_rows=listing.rejected_rows,
        free_rows=report.free_rows,
        trial_rows=report.trial_rows,
        unreadable_dates=report.unreadable_dates,
    )
    # The Desk's values are plan or type cells cut to 40 characters, any with an `@` redacted.
    if report.unknown_types:
        logger.warning(
            "roster_unknown_types run=%s dry_run=%s values=%s",
            run_id,
            dry_run,
            report.unknown_types,
        )
    if report.unreadable_dates:
        logger.warning(
            "roster_unreadable_dates run=%s dry_run=%s count=%s",
            run_id,
            dry_run,
            report.unreadable_dates,
        )
    if not listing.complete:
        counts["truncated"] = 1
        logger.error("alert=roster_truncated run=%s dry_run=%s", run_id, dry_run)
        raise _Stopped
    if report.unknown_plans:  # a plan the Desk cannot read could be a card payer: no guess
        counts["unknown_plans"] = len(report.unknown_plans)
        logger.error(
            "alert=roster_refused run=%s dry_run=%s reason=unknown_plans values=%s",
            run_id,
            dry_run,
            report.unknown_plans,
        )
        raise _Stopped

    paying_by_card = {
        e.contact_id
        for e in entitlements.existing_for(["substack_stripe"])
        if e.status in ("active", "grace")
    }
    existing = entitlements.existing_for(["substack_roster"])
    held_since = {e.contact_id: e.valid_from for e in existing}
    counts.update(card_payer_rows=0, card_payer_not_in_stripe=0, already_in_stripe=0)
    states: list[SourceState] = []
    for record in listing.records:
        contact_id = entitlements.contact_id_for(record.email)
        if not dry_run:
            counts["writing_contacts"] = 1  # from here a failure may have written some contacts
            entitlements.upsert_contact(
                record.email,
                ChannelsPatch(
                    substack={
                        "type": record.type,
                        "plan_interval": record.plan_interval,
                        "last_seen_in_roster": now.isoformat(),
                    }
                ),
            )
        if record.plan_interval is not None:  # a card payer: Stripe decides (ruling 2)
            counts["card_payer_rows"] += 1
            if contact_id not in paying_by_card:
                counts["card_payer_not_in_stripe"] += 1
            continue
        if contact_id in paying_by_card:  # Stripe already holds this reader (contracts, jobs)
            counts["already_in_stripe"] += 1
            continue
        states.append(
            SourceState(
                source="substack_roster",
                source_ref="roster",
                email=record.email,
                grant="status:substack_paid",
                status="active",
                started_at=record.since or held_since.get(contact_id) or listing.exported_at,
                valid_until=record.paid_until,
                plan_interval=None,
                access_scope="substack+platform",
                provider_time=listing.exported_at,
            )
        )

    plan = entitlements.plan_reconcile(existing, states, Guard(), now)
    counts.update(guard_ends=plan.ends, live_before=plan.live_before)
    if dry_run:
        counts.update(would_do(plan))
    else:
        counts["applying"] = 1  # from here a failure may have applied some writes
        applied = entitlements.apply_plan(plan, run_id, now)
        counts.update(
            created=applied.created,
            updated=applied.updated,
            ended=applied.ended,
            moved=applied.moved,
            unchanged=applied.unchanged,
            unseen=applied.unseen,
            grants_created=applied.grants_created,
            tier_changes=applied.tier_changes,
        )
    return "blocked" if plan.blocked else "passed"


def roster_import(dry_run: bool, now: datetime) -> SyncRun:
    rt = get_runtime()
    run_id = rt.runs.start(_KIND, dry_run, "owner", now)
    counts: dict[str, int] = {}
    try:
        guard = _work(dry_run, run_id, now, counts)
    except _Stopped:
        rt.runs.finish(run_id, "failed", None, counts, now)
    except Exception as exc:
        logger.error(
            "roster_failed run=%s dry_run=%s error=%s", run_id, dry_run, type(exc).__name__
        )
        rt.runs.finish(run_id, "failed", None, counts, now)
    else:
        rt.runs.finish(run_id, "completed", guard, counts, now)
        if guard == "blocked":
            logger.error("roster_guard_blocked run=%s dry_run=%s", run_id, dry_run)
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
