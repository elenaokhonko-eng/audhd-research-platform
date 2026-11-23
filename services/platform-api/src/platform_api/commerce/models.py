from datetime import datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


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


Audience = Literal["guests", "free_members", "paid_members"]


class Promotion(BaseModel):
    """The stored record (contracts section 4), written from the owner's private file.

    `display` and `substack_offer_url` are the owner's words and link; `counts` is written
    only by `count_once`, never from the file.
    """

    model_config = ConfigDict(extra="forbid")

    # No ':' and no '/': the id names a document and is half of the upgrade key
    # `{promotion_id}:{contact_id}`, which must not be the same for two pairs.
    id: str = Field(min_length=1, pattern=r"^[^:/]+$")
    channel: Literal["substack_offer", "platform_checkout"]
    audience: list[Audience]
    plan_interval: Literal["month", "year"] | None
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    substack_offer_url: str | None
    display: dict[str, str]
    counts: dict[str, int] = Field(default_factory=dict)  # upgrades_in_window
    updated_at: AwareDatetime | None = None
    updated_by: str | None = None

    @model_validator(mode="after")
    def _sound(self) -> Self:
        if self.starts_at >= self.ends_at:
            raise ValueError("a promotion must end after it starts")
        url = self.substack_offer_url
        if self.channel == "substack_offer" and url is not None and not url.startswith("https://"):
            raise ValueError("a Substack offer link starts with https://")
        return self


class PromotionView(BaseModel):
    """What a reader sees (contracts section 2). Never the counts."""

    id: str
    channel: Literal["substack_offer", "platform_checkout"]
    plan_interval: Literal["month", "year"] | None
    starts_at: datetime
    ends_at: datetime
    url: str | None
    display: dict[str, str]


class Route(BaseModel):
    kind: Literal["substack", "platform_only", "substack_change_plan"]
    available: bool
    url: str | None


class UpgradeOptions(BaseModel):
    routes: list[Route]
    promotion: PromotionView | None
