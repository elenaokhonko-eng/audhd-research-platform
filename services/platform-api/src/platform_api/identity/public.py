"""Sign-in, sessions and terms. The only way another module or the HTTP layer uses identity.

No address is ever put in an exception message, a log line, an event or a response: a member
is named by uid, a person by contact id, and the account page shows `email_hint` only.
"""

from datetime import datetime, timedelta
from typing import Literal
from uuid import uuid4

from platform_api.entitlements import public as entitlements
from platform_api.identity.models import (
    Join,
    JoinGrant,
    Member,
    MemberRef,
    MemberView,
    SessionCookie,
    SessionResult,
    SupportRequest,
    TermsAccepted,
    TermsVersions,
    TermsView,
)
from platform_api.identity.provider import InvalidToken
from platform_api.identity.runtime import get_runtime
from platform_api.shared.events import new_event
from platform_api.shared.http import ApiError

__all__ = [
    "JoinClosed",
    "Member",
    "MemberRef",
    "MemberView",
    "SessionResult",
    "SupportRequest",
    "Unauthenticated",
    "accept_terms",
    "end_sessions",
    "file_support_request",
    "list_support_requests",
    "member_count",
    "member_from_session",
    "member_view",
    "request_deletion",
    "resolve_session",
]

_SUBSTACK_SOURCES = ("substack_stripe", "substack_roster")


class Unauthenticated(PermissionError):
    """No valid member session. A PermissionError, so `shared.http` can refuse it by type."""


class JoinClosed(Exception):
    """A person with no member document tried to sign in while joining is switched off."""


def _owner_of(contact_id: str, now: datetime) -> str | None:
    view = entitlements.contact_view(contact_id, now)
    uid = view.channels.get("platform", {}).get("member_uid") if view else None
    return uid if isinstance(uid, str) else None


def _created_until(contact_id: str, created: list[str], now: datetime) -> JoinGrant | None:
    if not created:
        return None
    view = entitlements.contact_view(contact_id, now)
    ends = [
        r.reason.valid_until
        for r in (view.reasons if view else [])
        if r.entitlement_id in created and r.reason.valid_until is not None
    ]
    return JoinGrant(created=True, valid_until=max(ends) if ends else None)


def _check(uid: str, now: datetime) -> tuple[Literal["fresh", "started"], datetime | None]:
    """("fresh" or "started", when the sources were last checked)."""
    runtime = get_runtime()
    last = runtime.last_reconcile_at() if runtime.last_reconcile_at else None
    if runtime.request_refresh is None:
        return "fresh", last
    max_age = entitlements.launch_config().reconcile_max_age_seconds
    if last is not None and (now - last).total_seconds() <= max_age:
        return "fresh", last
    answer = runtime.request_refresh(uid, now)
    return ("fresh" if answer == "fresh" else "started"), last


def resolve_session(id_token: str, campaign_slug: str | None, now: datetime) -> SessionResult:
    """Turn a verified sign-in token into a member, their access and a session cookie."""
    runtime = get_runtime()
    try:
        identity = runtime.provider.verify_id_token(id_token)
    except InvalidToken:
        raise Unauthenticated("the sign-in was refused") from None
    if not identity.email_verified:
        raise Unauthenticated("the sign-in was refused")
    uid = identity.uid
    member = runtime.members.get(uid)
    if member is not None and member.status == "deletion_requested":
        raise Unauthenticated("the sign-in was refused")
    if member is None and not entitlements.launch_config().join_open:
        raise JoinClosed("joining is closed")

    first = member is None
    try:
        campaign = entitlements.campaign_by_slug(campaign_slug, now)
    except LookupError:
        campaign = None  # no default campaign is stored; nobody is turned away for that
    patch = entitlements.ChannelsPatch(
        platform={"member_uid": uid, "registered_at": now} if first else None
    )
    contact_id = entitlements.upsert_contact(identity.email, patch)
    if member is None:
        member = Member(
            uid=uid,
            primary_contact_id=contact_id,
            linked_contact_ids=[],
            email=identity.email,
            display_name=None,
            terms_accepted=None,
            joined_via=campaign.slug if campaign else None,
            status="active",
            created_at=now,
            last_seen_at=now,
        )
    else:
        member = member.model_copy(update={"last_seen_at": now})
    runtime.members.put(member)

    # The first writer of a contact's member_uid keeps it: another uid claims nothing.
    owns_contact = _owner_of(contact_id, now) == uid
    tier_before = None if first else entitlements.access_for(uid, now).tier
    created: list[str] = []
    if owns_contact:
        entitlements.claim_for_member(uid, contact_id)
        created = entitlements.apply_grant_policies(contact_id, now)
    access = entitlements.access_for(uid, now)
    recognition: Literal["paid", "free"] = (
        "paid"
        if access.tier == "paid"
        or any(
            r.source in _SUBSTACK_SOURCES and r.status in ("active", "grace")
            for r in access.reasons
        )
        else "free"
    )
    if first:
        if owns_contact and campaign is not None:
            entitlements.record_arrival(uid, campaign, recognition)
        runtime.bus.publish(
            new_event(
                "membership.member.registered",
                contact_id,
                {
                    "member_uid": uid,
                    "contact_id": contact_id,
                    "campaign": campaign.slug if campaign else None,
                },
                now=now,
            )
        )
    elif owns_contact:
        entitlements._announce_tier_change(
            contact_id, uid, tier_before, now, run_id="session", reason="sign_in"
        )
    check, checked_at = _check(uid, now)
    cookie = runtime.provider.create_session_cookie(id_token, runtime.session_ttl)
    return SessionResult(
        session=SessionCookie(cookie=cookie, expires_at=now + runtime.session_ttl),
        member=_view(member),
        access=access,
        join=Join(
            campaign=campaign.slug if campaign else None,
            recognition=recognition,
            source_checked_at=checked_at,
            check=check,
            grant=_created_until(contact_id, created, now),
        ),
    )


def member_from_session(cookie: str) -> MemberRef:
    """The member a session cookie belongs to. Refused when bad, revoked, or the member is gone."""
    runtime = get_runtime()
    try:
        uid = runtime.provider.verify_session_cookie(cookie)
    except InvalidToken:
        raise Unauthenticated("the session was refused") from None
    member = runtime.members.get(uid)
    if member is None or member.status != "active":
        raise Unauthenticated("the session was refused")
    return MemberRef(uid=uid, terms_ok=_terms_ok(member))


def end_sessions(uid: str) -> None:
    get_runtime().provider.revoke_sessions(uid)


def _required() -> TermsVersions:
    config = entitlements.launch_config()
    return TermsVersions(
        terms_version=config.required_terms_version,
        privacy_version=config.required_privacy_version,
    )


def _terms_ok(member: Member) -> bool:
    held = member.terms_accepted
    required = _required()
    return (
        held is not None
        and bool(required.terms_version and required.privacy_version)
        and held.terms_version == required.terms_version
        and held.privacy_version == required.privacy_version
    )


def _email_hint(email: str) -> str:
    local, sep, domain = email.strip().rpartition("@")
    if not sep or not local or not domain:
        return "…"
    return f"{local[0]}…@{domain}"


def _view(member: Member) -> MemberView:
    held = member.terms_accepted
    return MemberView(
        uid=member.uid,
        display_name=member.display_name,
        email_hint=_email_hint(member.email),
        terms=TermsView(
            accepted=_terms_ok(member),
            terms_version=held.terms_version if held else None,
            privacy_version=held.privacy_version if held else None,
            required=_required(),
        ),
        joined_via=member.joined_via,
        status=member.status,
    )


def _member(uid: str) -> Member:
    member = get_runtime().members.get(uid)
    if member is None:
        raise LookupError("no such member")
    return member


def member_view(uid: str) -> MemberView:
    return _view(_member(uid))


def accept_terms(uid: str, terms_version: str, privacy_version: str, now: datetime) -> MemberView:
    """Record acceptance of exactly the versions now required; any other version is refused."""
    required = _required()
    if (
        not required.terms_version
        or not required.privacy_version
        or terms_version != required.terms_version
        or privacy_version != required.privacy_version
    ):
        raise ApiError(
            422, "validation_failed", "These are not the terms and privacy notice now in force."
        )
    accepted = TermsAccepted(terms_version=terms_version, privacy_version=privacy_version, at=now)
    member = _member(uid).model_copy(update={"terms_accepted": accepted})
    get_runtime().members.put(member)
    return _view(member)


def request_deletion(uid: str, now: datetime) -> None:
    """Mark the member for deletion and end every session they hold. They cannot sign in again."""
    member = _member(uid).model_copy(update={"status": "deletion_requested"})
    get_runtime().members.put(member)
    end_sessions(uid)


def member_count() -> int:
    return get_runtime().members.count()


_SUPPORT_LIMIT = 5
_SUPPORT_WINDOW = timedelta(days=1)


def file_support_request(
    uid: str, kind: Literal["paid_not_recognised", "other"], note: str, now: datetime
) -> str:
    """Store a request and announce it. The note stays in the store: the event has uid and kind."""
    runtime = get_runtime()
    wait = runtime.limiter.hit(f"support:{uid}", _SUPPORT_LIMIT, _SUPPORT_WINDOW, now)
    if wait is not None:
        raise ApiError(
            429, "rate_limited", "Too many requests today; please try later.", retry_after=wait
        )
    request = SupportRequest(
        id=uuid4().hex, member_uid=uid, kind=kind, note=note, status="open", created_at=now
    )
    runtime.members.add_support_request(request)
    runtime.bus.publish(
        new_event("membership.support.requested", uid, {"member_uid": uid, "kind": kind}, now=now)
    )
    return request.id


def list_support_requests() -> list[SupportRequest]:
    """Every stored request, oldest first."""
    return get_runtime().members.support_requests()
