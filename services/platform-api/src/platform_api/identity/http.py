from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from platform_api.entitlements.public import access_for
from platform_api.identity import public
from platform_api.identity.public import MemberRef
from platform_api.shared import clock
from platform_api.shared.http import ApiError, current_member, member_with_terms

router = APIRouter()
hooks_router = APIRouter()

Signed = Annotated[MemberRef, Depends(current_member)]
Termed = Annotated[MemberRef, Depends(member_with_terms)]


class ResolveBody(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    id_token: str
    campaign: str | None = None


class TermsBody(BaseModel):
    terms_version: str
    privacy_version: str


class SupportBody(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    kind: Literal["paid_not_recognised", "other"]
    note: str = Field(max_length=500, repr=False)


@router.post("/v1/session/resolve")
def resolve(body: ResolveBody) -> dict[str, Any]:
    """Called by `web` with its service identity, after the person signed in."""
    try:
        result = public.resolve_session(body.id_token, body.campaign, clock.utcnow())
    except public.Unauthenticated:
        raise ApiError(401, "unauthenticated", "The sign-in could not be confirmed.") from None
    except public.JoinClosed:
        raise ApiError(403, "forbidden", "Joining is closed at the moment.") from None
    return result.model_dump(mode="json")


@router.post("/v1/session/revoke")
def revoke(member: Signed) -> dict[str, Any]:
    public.end_sessions(member.uid)
    return {}


def _gone() -> ApiError:
    """The member was removed after the session was checked: a refusal, not a fault."""
    return ApiError(401, "unauthenticated", "Please sign in.")


@router.get("/v1/me")
def me(member: Signed) -> dict[str, Any]:
    try:
        view = public.member_view(member.uid)
    except LookupError:
        raise _gone() from None
    return {
        "member": view.model_dump(mode="json"),
        "access": access_for(member.uid, clock.utcnow()).model_dump(mode="json"),
    }


@router.post("/v1/me/terms-acceptance")
def accept_terms(member: Signed, body: TermsBody) -> dict[str, Any]:
    try:
        view = public.accept_terms(
            member.uid, body.terms_version, body.privacy_version, clock.utcnow()
        )
    except LookupError:
        raise _gone() from None
    return {"member": view.model_dump(mode="json")}


@router.post("/v1/me/deletion-request")
def deletion_request(member: Signed) -> dict[str, str]:
    try:
        public.request_deletion(member.uid, clock.utcnow())
    except LookupError:
        raise _gone() from None
    return {"status": "deletion_requested"}


@router.post("/v1/me/support-requests")
def support_request(member: Termed, body: SupportBody) -> dict[str, str]:
    """The body is validated before the limiter is hit, so a refused body costs no quota."""
    request_id = public.file_support_request(member.uid, body.kind, body.note, clock.utcnow())
    return {"id": request_id}
