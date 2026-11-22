"""The owner's routes. Every one sits behind `owner` and writes an audit entry, reads included.

An address arrives only in a request body. It is never logged, never returned, and never
repeated in an error message.
"""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from platform_api.admin.models import CampaignsBody, GrantBody, LaunchBody, RevokeBody, SearchBody
from platform_api.admin.public import owner
from platform_api.entitlements import public as entitlements
from platform_api.identity import public as identity
from platform_api.shared import clock
from platform_api.shared.http import ApiError

router = APIRouter(dependencies=[Depends(owner)])
hooks_router = APIRouter()

Owner = Annotated[str, Depends(owner)]  # resolved once per request, with the router's

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _audit(account: str, action: str, subject: str, route: str) -> None:
    entitlements.write_audit(
        entitlements.AuditEntry(
            at=clock.utcnow(),
            actor=f"owner:{account}",
            action=action,
            subject=subject,
            reason=None,
            evidence={"route": route},
        )
    )


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation_failed", message)


@router.post("/v1/admin/contacts/search")
def search_contact(body: SearchBody, account: Owner) -> dict[str, Any]:
    """Looks a contact up by address. Creates nothing; `{contact: null}` when there is none."""
    now = clock.utcnow()
    try:
        contact_id = entitlements.contact_id_for(body.email)
    except ValueError:
        raise _invalid("This is not an email address.") from None
    view = entitlements.contact_view(contact_id, now)
    _audit(account, "admin.read", contact_id if view else "admin", "contacts/search")
    if view is None:
        return {"contact": None}
    return {
        "contact": {
            "contact_id": view.contact_id,
            "channels": view.channels,
            "has_member": view.has_member,
            "entitlements": [
                {"entitlement_id": r.entitlement_id, **r.reason.model_dump(mode="json")}
                for r in view.reasons
            ],
            "audit": [a.model_dump(mode="json") for a in view.audit],
        }
    }


@router.post("/v1/admin/entitlements")
def create_grant(body: GrantBody, account: Owner) -> dict[str, str]:
    """A grant by hand. `grant` itself writes the audit entry, under the owner's account."""
    now = clock.utcnow()
    valid_until = (
        clock.add_months(now, body.months) if body.months is not None else body.valid_until
    )
    if valid_until is None or valid_until <= now:
        raise _invalid("The grant must end after today.")
    try:
        contact_id = entitlements.upsert_contact(body.email, entitlements.ChannelsPatch())
        entitlement_id = entitlements.grant(
            contact_id, body.grant, valid_until, body.reason, f"owner:{account}", now
        )
    except ValueError:
        raise _invalid(
            "The grant was refused. A grant is tier:paid or item:<sku>, the address must be "
            "valid, the reason must be filled in without an address, and the same grant must "
            "not exist already."
        ) from None
    except LookupError:
        raise ApiError(404, "not_found", "There is no such contact.") from None
    return {"entitlement_id": entitlement_id}


@router.post("/v1/admin/entitlements/{entitlement_id}/revoke")
def revoke_grant(entitlement_id: str, body: RevokeBody, account: Owner) -> dict[str, Any]:
    """`revoke` itself writes the audit entry, under the owner's account."""
    try:
        entitlements.revoke(entitlement_id, body.reason, f"owner:{account}", clock.utcnow())
    except LookupError:
        raise ApiError(404, "not_found", "There is no such entitlement.") from None
    except ValueError:
        raise _invalid(
            "Only a grant can be revoked by hand, with a reason that holds no address."
        ) from None
    return {}


@router.put("/v1/admin/campaigns")
def put_campaigns(body: CampaignsBody, account: Owner) -> dict[str, int]:
    """Exactly one default once the file is merged by slug with what is stored; unique slugs."""
    slugs = [c.slug for c in body.campaigns]
    if len(set(slugs)) != len(slugs):
        raise _invalid("A campaign slug is named more than once.")
    merged = {c.slug: c for c in entitlements.list_campaigns()}
    merged.update({c.slug: c for c in body.campaigns})
    if sum(c.is_default for c in merged.values()) != 1:
        raise _invalid("Exactly one campaign must be the default.")
    try:
        written = entitlements.put_campaigns(body.campaigns, f"owner:{account}")
    except ValueError:
        raise _invalid("The campaigns were refused: check the slugs and the default.") from None
    _audit(account, "campaign.written", "admin", "campaigns")
    return {"written": written}


@router.put("/v1/admin/launch")
def put_launch(body: LaunchBody, account: Owner) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    try:
        config = entitlements.update_launch_config(patch, f"owner:{account}")
    except ValueError:
        raise _invalid("These are not launch settings.") from None
    _audit(account, "launch.switched", "admin", "launch")
    return config.model_dump(mode="json")


@router.get("/v1/admin/launch/report")
def launch_report(account: Owner) -> dict[str, Any]:
    now = clock.utcnow()
    config = entitlements.launch_config()
    campaigns = [
        {
            "slug": c.slug,
            "state": entitlements.campaign_state(c, config, now),
            "counts": dict(c.counts),
        }
        for c in entitlements.list_campaigns()
    ]
    members = identity.member_count()
    _audit(account, "admin.read", "admin", "launch/report")
    return {"campaigns": campaigns, "members": members}


@router.get("/v1/admin/support-requests")
def support_requests(account: Owner) -> dict[str, Any]:
    """A note is the member's own words; anything shaped like an address in it is masked."""
    requests = [
        {
            **r.model_dump(mode="json", include={"id", "member_uid", "kind", "created_at"}),
            "note": _EMAIL.sub("[email]", r.note),
        }
        for r in identity.list_support_requests()
    ]
    _audit(account, "admin.read", "admin", "support-requests")
    return {"requests": requests}
