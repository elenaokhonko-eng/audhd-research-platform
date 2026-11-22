from datetime import UTC, datetime, timedelta
from typing import Any

from platform_api.entitlements.models import Entitlement, entitlement_id
from platform_api.shared.clock import add_months

EMAIL: dict[str, str] = {
    name: f"{name}@example.org" for name in ("ana", "bo", "cy", "di", "ed", "fay", "gus", "hal")
}

T0 = datetime(2026, 11, 20, tzinfo=UTC)

CUT_OFF = T0 - timedelta(days=30)

_DEFAULTS: dict[str, dict[str, Any]] = {
    "stripe_year": dict(
        source="substack_stripe",
        grant="tier:paid",
        plan_interval="year",
        access_scope="substack+platform",
        valid_from=T0 - timedelta(days=200),
        valid_until=T0 + timedelta(days=165),
    ),
    "stripe_month_status": dict(
        source="substack_stripe",
        grant="status:substack_paid",
        plan_interval="month",
        access_scope="substack+platform",
        valid_from=T0 - timedelta(days=200),
        valid_until=T0 + timedelta(days=165),
    ),
    "roster_status": dict(
        source="substack_roster",
        source_ref="roster",
        grant="status:substack_paid",
        plan_interval=None,
        access_scope="substack+platform",
        valid_from=T0 - timedelta(days=200),
        valid_until=None,
    ),
    "launch_grant": dict(
        source="grant",
        source_ref="campaign:founding",
        grant="tier:paid",
        plan_interval=None,
        access_scope="platform_only",
        valid_from=T0,
        valid_until=add_months(T0, 6),
    ),
    "owner_grant": dict(
        source="grant",
        source_ref="owner:test",
        grant="tier:paid",
        plan_interval=None,
        access_scope="platform_only",
        valid_from=T0,
        valid_until=None,
    ),
    "item": dict(
        source="payhip",
        grant="item:sample",
        plan_interval=None,
        access_scope="platform_only",
        valid_from=T0,
        valid_until=None,
    ),
}


def record(name: str, kind: str, **over: Any) -> Entitlement:
    fields: dict[str, Any] = {
        "contact_id": f"c-{name}",
        "member_uid": None,
        "status": "active",
        "updated_at": T0,
        "updated_by": "run:test",
        "source_ref": f"sub_{name}" if kind.startswith("stripe") else f"sale_{name}",
        **_DEFAULTS[kind],
    }
    if kind == "stripe_month_status" and name == "cy":
        fields["valid_from"] = T0 - timedelta(days=5)
    fields.update(over)
    fields["entitlement_id"] = entitlement_id(
        fields["source"], fields["source_ref"], fields["contact_id"], fields["grant"]
    )
    return Entitlement(**fields)


def holdings(name: str) -> list[Entitlement]:
    """Each person's records under the settings in force."""
    if name in ("bo", "ed"):
        return []
    return {
        "ana": [record("ana", "stripe_year"), record("ana", "launch_grant")],
        "cy": [record("cy", "stripe_month_status")],
        "di": [record("di", "roster_status")],
        "fay": [record("fay", "stripe_year", status="expired"), record("fay", "launch_grant")],
        "gus": [record("gus", "stripe_year"), record("gus", "roster_status")],
        "hal": [record("hal", "stripe_month_status")],
    }[name]
