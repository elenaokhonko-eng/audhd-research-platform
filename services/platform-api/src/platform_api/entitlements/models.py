"""Entitlement records. Frozen; every datetime is timezone-aware."""

import hashlib
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Source = Literal["substack_stripe", "substack_roster", "platform_stripe", "payhip", "grant"]
Status = Literal["active", "grace", "expired", "revoked"]
PlanInterval = Literal["month", "year"]


class Entitlement(BaseModel):
    model_config = ConfigDict(frozen=True)

    entitlement_id: str
    contact_id: str
    member_uid: str | None
    grant: str  # "tier:paid", "status:substack_paid", "item:<sku>"
    source: Source
    source_ref: str
    access_scope: Literal["substack+platform", "platform_only"] | None
    plan_interval: PlanInterval | None
    valid_from: AwareDatetime | None
    valid_until: AwareDatetime | None
    status: Status
    updated_at: AwareDatetime
    updated_by: str  # "run:<run_id>", "member:<uid>", "owner:<account id>", "policy:<slug>"


class SourceState(BaseModel):
    """What a source says now about one grant for one person."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    source: Literal["substack_stripe", "substack_roster", "platform_stripe"]
    source_ref: str  # Stripe subscription id, or "roster"
    email: str = Field(
        repr=False
    )  # used only to compute contact_id; never stored on the entitlement
    grant: str  # "tier:paid" or "status:substack_paid", chosen per plan interval by settings
    status: Literal["active", "grace", "expired"]
    started_at: (
        AwareDatetime | None
    )  # when the source says the paid period began; becomes valid_from
    valid_until: AwareDatetime | None
    plan_interval: Literal["month", "year"] | None
    access_scope: Literal["substack+platform", "platform_only"]
    provider_time: AwareDatetime


class ChannelsPatch(BaseModel):
    """What a caller knows about one channel; unset fields change nothing."""

    model_config = ConfigDict(frozen=True)

    substack: dict[str, object] | None = None
    stripe: dict[str, object] | None = None
    platform: dict[str, object] | None = None


class Contact(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    contact_id: str
    key_version: str
    email: str = Field(repr=False)
    channels: dict[str, dict[str, object]]
    invite: dict[str, object]  # {"campaign": slug or None, "state": "none" | "accepted"}
    created_at: AwareDatetime
    updated_at: AwareDatetime


class AuditEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: AwareDatetime
    actor: str  # same form as Entitlement.updated_by
    action: str
    subject: str  # an id, never an address
    reason: str | None
    evidence: dict[str, str]  # ids only


class Reason(BaseModel):
    """Why a member holds something, in terms a person can read."""

    model_config = ConfigDict(frozen=True)

    grant: str
    source: Source
    label: Literal[
        "substack_subscription",
        "substack_status",
        "platform_subscription",
        "launch_grant",
        "owner_grant",
        "purchase",
    ]
    access_scope: Literal["substack+platform", "platform_only"] | None
    status: Status
    valid_until: AwareDatetime | None
    campaign: str | None
    plan_interval: PlanInterval | None


class Access(BaseModel):
    """Always computed, never stored."""

    model_config = ConfigDict(frozen=True)

    tier: Literal["free", "paid"]
    sections: list[str]
    items: list[str]
    reasons: list[Reason]
    computed_at: AwareDatetime


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: Literal["paid_required", "purchase_required"] | None


def entitlement_id(source: str, source_ref: str, contact_id: str, grant: str) -> str:
    text = f"{source}:{source_ref}:{contact_id}:{grant}"
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def normalise_email(value: str) -> str:
    """Trim and lower-case. The error never repeats the value."""
    cleaned = value.strip().lower()
    local, sep, domain = cleaned.partition("@")
    if not sep or not local or not domain or "@" in domain:
        raise ValueError("not an email address")
    return cleaned
