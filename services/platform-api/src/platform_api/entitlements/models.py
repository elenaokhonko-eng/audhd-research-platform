"""Entitlement records. Frozen; every datetime is timezone-aware."""

import hashlib
import re
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

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


class ReasonEntry(BaseModel):
    """One record of a contact and why it counts, for the owner's view."""

    model_config = ConfigDict(frozen=True)

    entitlement_id: str
    reason: Reason


class ContactView(BaseModel):
    """What the owner sees of one contact. Never the address."""

    model_config = ConfigDict(frozen=True)

    contact_id: str
    channels: dict[str, dict[str, object]]
    has_member: bool
    reasons: list[ReasonEntry]
    audit: list[AuditEntry]


class GrantPolicy(BaseModel):
    """When a campaign gives a launch grant (design 5.4)."""

    model_config = ConfigDict(frozen=True)

    grant: Literal["tier:paid"]
    months: int | None  # required when starts is "at_claim"
    starts: Literal["at_claim", "fixed"]
    fixed_until: AwareDatetime | None  # required when starts is "fixed"
    requires_live_source: list[Source]
    paid_since_before: AwareDatetime | None
    plan_intervals: list[PlanInterval] | None

    @model_validator(mode="after")
    def _complete(self) -> Self:
        if self.starts == "at_claim" and (self.months is None or self.months < 1):
            raise ValueError("a policy that starts at the claim needs a number of months")
        if self.starts == "fixed" and self.fixed_until is None:
            raise ValueError("a policy with a fixed end needs fixed_until")
        if "grant" in self.requires_live_source:
            raise ValueError("a grant never earns another grant")
        return self


_SLUG = re.compile(r"[a-z0-9-]{1,40}")  # used with fullmatch: "$" would allow a final newline


class Campaign(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    slug: str
    audience: Literal["substack_paid", "substack_free", "public"]
    opens_at: AwareDatetime | None
    closes_at: AwareDatetime | None
    is_default: bool
    grant: GrantPolicy | None
    # headline, body, cta. The plain name would shadow BaseModel.copy; dump with by_alias=True.
    copy_: dict[str, str] = Field(alias="copy")
    counts: dict[str, int]  # arrivals, recognised_paid, grants_created

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str) -> str:
        if not _SLUG.fullmatch(value) or value == "default":
            raise ValueError(
                "a slug is 1 to 40 lower-case letters, digits or hyphens, and not 'default'"
            )
        return value


class GrantSpec(BaseModel):
    """A launch grant that is due: who, from which campaign, until when, on what evidence."""

    model_config = ConfigDict(frozen=True)

    campaign: str
    contact_id: str
    grant: str
    valid_until: AwareDatetime
    evidence_entitlement_id: str


class LaunchConfig(BaseModel):
    """The `config/launch` document: the owner's switches."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    join_open: bool = False
    library_open: bool = False
    promotions_open: bool = False
    reconcile_max_age_seconds: int = 900
    required_terms_version: str = ""
    required_privacy_version: str = ""
    substack_account_url: str = ""


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
