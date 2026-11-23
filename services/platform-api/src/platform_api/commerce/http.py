from typing import Annotated, Any

from fastapi import APIRouter, Depends

from platform_api.commerce.ports import JobStartError
from platform_api.commerce.refresh import RateLimited, request_refresh
from platform_api.identity.public import MemberRef
from platform_api.shared import clock
from platform_api.shared.http import ApiError, member_with_terms

router = APIRouter()
hooks_router = APIRouter()

Termed = Annotated[MemberRef, Depends(member_with_terms)]


@router.post("/v1/me/refresh-access", status_code=202)
def refresh_access(member: Termed) -> dict[str, Any]:
    """'Check again': `web` then polls `GET /v1/me`."""
    try:
        ticket = request_refresh(member.uid, clock.utcnow())
    except RateLimited as limited:
        raise ApiError(
            429, "rate_limited", "Please wait a moment before checking again.", limited.retry_after
        ) from None
    except JobStartError:
        raise ApiError(
            503, "unavailable", "The check could not be started. Please try again later."
        ) from None
    return ticket.model_dump(mode="json")
