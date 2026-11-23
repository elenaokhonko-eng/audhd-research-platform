from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class StripeSubscription(BaseModel):
    """Stripe's subscription reduced to what the rules need."""

    model_config = ConfigDict(hide_input_in_errors=True)

    id: str
    status: Literal[
        "trialing",
        "active",
        "past_due",
        "incomplete",
        "incomplete_expired",
        "canceled",
        "unpaid",
        "paused",
    ]
    application: str | None  # the Connect application that created it
    metadata: dict[str, str] = Field(repr=False)
    customer_email: str | None = Field(default=None, repr=False)
    interval: Literal["day", "week", "month", "year"] | None
    start_date: AwareDatetime
    current_period_end: AwareDatetime | None
    past_due_since: AwareDatetime | None  # set only while past_due
    provider_time: AwareDatetime  # when the list call returned


RunKind = Literal["stripe_reconcile", "roster_import"]
RequestedBy = Literal["schedule", "member", "owner"]


class SyncRun(BaseModel):
    """One run of a sync job. Counts only; never an address."""

    run_id: str
    kind: RunKind
    dry_run: bool
    state: Literal["running", "completed", "failed"]
    guard: Literal["passed", "blocked"] | None
    requested_by: RequestedBy
    counts: dict[str, int]
    started_at: datetime
    finished_at: datetime | None


class RefreshTicket(BaseModel):
    """The answer to "Check again". Ids only; never an address."""

    check: Literal["fresh", "started", "already_running"]
    last_completed_at: datetime | None
    next_allowed_at: datetime
