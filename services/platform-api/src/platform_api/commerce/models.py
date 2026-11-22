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
