"""Members and what sign-in returns. Every datetime is timezone-aware."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from platform_api.entitlements.public import Access


class TermsAccepted(BaseModel):
    """The versions a member accepted, and when."""

    model_config = ConfigDict(frozen=True)

    terms_version: str
    privacy_version: str
    at: AwareDatetime


class Member(BaseModel):
    """The stored `members/{uid}` document."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    uid: str
    primary_contact_id: str
    linked_contact_ids: list[str]
    email: str = Field(repr=False)
    display_name: str | None
    terms_accepted: TermsAccepted | None
    joined_via: str | None
    status: Literal["active", "deletion_requested"]
    created_at: AwareDatetime
    last_seen_at: AwareDatetime


class SupportRequest(BaseModel):
    """A stored `support_requests/{id}` document. The note lives here and nowhere else."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    id: str
    member_uid: str
    kind: Literal["paid_not_recognised", "other"]
    note: str = Field(repr=False)
    status: Literal["open"]
    created_at: AwareDatetime


class TermsVersions(BaseModel):
    model_config = ConfigDict(frozen=True)

    terms_version: str
    privacy_version: str


class TermsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    terms_version: str | None
    privacy_version: str | None
    required: TermsVersions


class MemberView(BaseModel):
    """The Member shape of contracts section 2. Never the address, only a hint."""

    model_config = ConfigDict(frozen=True)

    uid: str
    display_name: str | None
    email_hint: str
    terms: TermsView
    joined_via: str | None
    status: Literal["active", "deletion_requested"]


class MemberRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    uid: str
    terms_ok: bool


class JoinGrant(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: bool
    valid_until: AwareDatetime | None


class Join(BaseModel):
    """What happened at this sign-in."""

    model_config = ConfigDict(frozen=True)

    campaign: str | None
    recognition: Literal["paid", "free"]
    source_checked_at: AwareDatetime | None
    check: Literal["fresh", "started"]
    grant: JoinGrant | None


class SessionCookie(BaseModel):
    model_config = ConfigDict(frozen=True)

    cookie: str
    expires_at: AwareDatetime


class SessionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    session: SessionCookie
    member: MemberView
    access: Access
    join: Join
