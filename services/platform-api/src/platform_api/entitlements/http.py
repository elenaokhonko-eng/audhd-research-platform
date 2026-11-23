from typing import Annotated, Any

from fastapi import APIRouter, Depends

from platform_api.entitlements import public
from platform_api.entitlements.campaigns import campaign_state
from platform_api.shared import clock
from platform_api.shared.http import ApiError, member_with_terms

router = APIRouter()
hooks_router = APIRouter()


@router.get("/v1/public/campaigns/{slug}")
def get_campaign(slug: str) -> dict[str, Any]:
    """A campaign's public face. An unknown slug gets the default campaign, with slug null."""
    now = clock.utcnow()
    try:
        campaign = public.campaign_by_slug(slug, now)
    except LookupError:
        raise ApiError(404, "not_found", "There is no campaign to show.") from None
    shown = campaign.model_dump(by_alias=True, include={"slug", "audience", "copy_"})
    return {
        "slug": campaign.slug if campaign.slug == slug else None,
        "audience": shown["audience"],
        "state": campaign_state(campaign, public.launch_config(), now),
        "copy": shown["copy"],
    }


@router.get("/v1/me/entitlements")
def my_entitlements(member: Annotated[Any, Depends(member_with_terms)]) -> dict[str, Any]:
    reasons = public.access_for(member.uid, clock.utcnow()).reasons
    return {"entitlements": [r.model_dump(mode="json") for r in reasons]}
