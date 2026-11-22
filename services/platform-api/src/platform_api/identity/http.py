from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from platform_api.entitlements.public import access_for
from platform_api.identity import public
from platform_api.identity.public import MemberRef
from platform_api.shared import clock
from platform_api.shared.http import ApiError, current_member

router = APIRouter()
hooks_router = APIRouter()

Signed = Annotated[MemberRef, Depends(current_member)]


class ResolveBody(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    id_token: str
    campaign: str | None = None


class TermsBody(BaseModel):
    terms_version: str
    privacy_version: str


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


@router.get("/v1/me")
def me(member: Signed) -> dict[str, Any]:
    return {
        "member": public.member_view(member.uid).model_dump(mode="json"),
        "access": access_for(member.uid, clock.utcnow()).model_dump(mode="json"),
    }


@router.post("/v1/me/terms-acceptance")
def accept_terms(member: Signed, body: TermsBody) -> dict[str, Any]:
    view = public.accept_terms(member.uid, body.terms_version, body.privacy_version, clock.utcnow())
    return {"member": view.model_dump(mode="json")}


@router.post("/v1/me/deletion-request")
def deletion_request(member: Signed) -> dict[str, str]:
    public.request_deletion(member.uid, clock.utcnow())
    return {"status": "deletion_requested"}
