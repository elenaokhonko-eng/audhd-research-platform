from datetime import datetime, timedelta
from typing import Literal

from platform_api.commerce.models import StripeSubscription
from platform_api.commerce.settings import CommerceSettings
from platform_api.entitlements.public import SourceState, normalise_email

Channel = Literal["substack", "platform"]
Skip = Literal["not_substack", "no_address", "bad_address", "incomplete", "past_due_unknown"]


def classify(sub: StripeSubscription, settings: CommerceSettings) -> Channel | None:
    if (
        settings.stripe_substack_application
        and sub.application == settings.stripe_substack_application
    ):
        return "substack"
    if settings.stripe_test_channel_metadata and sub.metadata.get("test_channel") == "substack":
        return "substack"
    return None


def to_state(
    sub: StripeSubscription, settings: CommerceSettings, now: datetime
) -> SourceState | Skip:
    if classify(sub, settings) != "substack":
        return "not_substack"
    if sub.customer_email is None:
        return "no_address"
    try:
        email = normalise_email(sub.customer_email)
    except ValueError:
        return "bad_address"

    status: Literal["active", "grace", "expired"]
    if sub.status in ("trialing", "active"):
        status, valid_until = "active", sub.current_period_end
    elif sub.status == "past_due":
        if sub.past_due_since is None:
            return "past_due_unknown"  # nothing ends on missing information
        ends = sub.past_due_since + timedelta(days=settings.grace_days)
        status, valid_until = ("grace", ends) if now < ends else ("expired", now)
    elif sub.status == "incomplete":
        return "incomplete"
    else:  # canceled, unpaid, incomplete_expired, paused
        status, valid_until = "expired", now

    interval = sub.interval if sub.interval in ("month", "year") else None
    grant = (
        settings.substack_grant_year if sub.interval == "year" else settings.substack_grant_month
    )
    return SourceState(
        source="substack_stripe",
        source_ref=sub.id,
        email=email,
        grant=grant,
        status=status,
        started_at=sub.start_date,
        valid_until=valid_until,
        plan_interval=interval,
        access_scope="substack+platform",
        provider_time=sub.provider_time,
    )
