"""The owner's routes. Every one sits behind `owner`, and every call by a verified owner leaves
exactly one route-level audit entry, reads and refusals included.

An address arrives only in a request body. It is never logged, never returned, and never
repeated in an error message.
"""

import re
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from platform_api.admin.models import CampaignsBody, GrantBody, LaunchBody, RevokeBody, SearchBody
from platform_api.admin.public import owner
from platform_api.entitlements import public as entitlements
from platform_api.identity import public as identity
from platform_api.shared import clock
from platform_api.shared.http import ApiError

# (method, path) -> (route name for the evidence, audit action). A route missing here cannot be
# added to the router: AuditedRoute refuses it.
AUDIT_ACTIONS: dict[tuple[str, str], tuple[str, str]] = {
    ("POST", "/v1/admin/contacts/search"): ("contacts/search", "admin.read"),
    ("POST", "/v1/admin/entitlements"): ("entitlements", "entitlement.granted"),
    ("POST", "/v1/admin/entitlements/{entitlement_id}/revoke"): (
        "entitlements/revoke",
        "entitlement.revoked",
    ),
    ("PUT", "/v1/admin/campaigns"): ("campaigns", "campaign.written"),
    ("PUT", "/v1/admin/launch"): ("launch", "launch.switched"),
    ("GET", "/v1/admin/launch/report"): ("launch/report", "admin.read"),
    ("GET", "/v1/admin/support-requests"): ("support-requests", "admin.read"),
}

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _subject(request: Request) -> str:
    """What the route named (`about`), else the entitlement id of the path, else `admin`."""
    subject = getattr(request.state, "audit_subject", None) or request.path_params.get(
        "entitlement_id"
    )
    return subject if isinstance(subject, str) and subject and "@" not in subject else "admin"


def _status_of(exc: Exception) -> int:
    if isinstance(exc, ApiError):
        return exc.status
    if isinstance(exc, RequestValidationError):
        return 422
    if isinstance(exc, StarletteHTTPException):
        return exc.status_code
    return 500


class AuditedRoute(APIRoute):
    """Writes one audit entry after every call by a verified owner, once the outcome is known.

    A caller that `owner` refused named no account and is not audited.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        declared = {AUDIT_ACTIONS.get((m.upper(), path)) for m in kwargs.get("methods") or ()}
        found = declared.pop() if len(declared) == 1 else None
        if found is None:
            raise RuntimeError(f"no audit action is declared for the admin route {path!r}")
        self.audit_route, self.audit_action = found
        super().__init__(path, endpoint, **kwargs)

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()
        route, action = self.audit_route, self.audit_action

        async def audited(request: Request) -> Response:
            status = 500
            try:
                response = await handler(request)
                status = response.status_code
                return response
            except Exception as exc:
                status = _status_of(exc)
                raise
            finally:
                account = getattr(request.state, "owner_account", None)
                if isinstance(account, str):
                    entry = entitlements.AuditEntry(
                        at=clock.utcnow(),
                        actor=f"owner:{account}",
                        action=action,
                        subject=_subject(request),
                        reason=None,
                        evidence={"route": route, "outcome": str(status)},
                    )
                    await run_in_threadpool(entitlements.write_audit, entry)

        return audited


router = APIRouter(dependencies=[Depends(owner)], route_class=AuditedRoute)
hooks_router = APIRouter()

Owner = Annotated[str, Depends(owner)]  # resolved once per request, with the router's


def _about(request: Request, subject: str) -> None:
    """Name the entitlement or contact this call is about, for its audit entry."""
    request.state.audit_subject = subject


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation_failed", message)


@router.post("/v1/admin/contacts/search")
def search_contact(request: Request, body: SearchBody) -> dict[str, Any]:
    """Looks a contact up by address. Creates nothing; `{contact: null}` when there is none."""
    now = clock.utcnow()
    try:
        contact_id = entitlements.contact_id_for(body.email)
    except ValueError:
        raise _invalid("This is not an email address.") from None
    view = entitlements.contact_view(contact_id, now)
    if view is None:
        return {"contact": None}
    _about(request, contact_id)
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
def create_grant(request: Request, body: GrantBody, account: Owner) -> dict[str, str]:
    """A grant by hand. `grant` also records the grant itself in the audit log."""
    now = clock.utcnow()
    valid_until = (
        clock.add_months(now, body.months) if body.months is not None else body.valid_until
    )
    if valid_until is None or valid_until <= now:
        raise _invalid("The grant must end after today.")
    try:
        contact_id = entitlements.upsert_contact(body.email, entitlements.ChannelsPatch())
        _about(request, contact_id)
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
    _about(request, entitlement_id)
    return {"entitlement_id": entitlement_id}


@router.post("/v1/admin/entitlements/{entitlement_id}/revoke")
def revoke_grant(entitlement_id: str, body: RevokeBody, account: Owner) -> dict[str, Any]:
    """`revoke` also records the change itself, unless the grant was revoked already."""
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
    """Each slug once, and exactly one default once the file is merged with what is stored."""
    try:
        written = entitlements.put_campaigns(body.campaigns, f"owner:{account}")
    except ValueError:
        raise _invalid(
            "The campaigns were refused. Name each slug once, and leave exactly one default "
            "once the file is merged with the stored campaigns."
        ) from None
    return {"written": written}


@router.put("/v1/admin/launch")
def put_launch(body: LaunchBody, account: Owner) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    try:
        config = entitlements.update_launch_config(patch, f"owner:{account}")
    except ValueError:
        raise _invalid("These are not launch settings.") from None
    return config.model_dump(mode="json")


@router.get("/v1/admin/launch/report")
def launch_report() -> dict[str, Any]:
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
    return {"campaigns": campaigns, "members": identity.member_count()}


@router.get("/v1/admin/support-requests")
def support_requests() -> dict[str, Any]:
    """A note is the member's own words; anything shaped like an address in it is masked."""
    requests = [
        {
            **r.model_dump(mode="json", include={"id", "member_uid", "kind", "created_at"}),
            "note": _EMAIL.sub("[email]", r.note),
        }
        for r in identity.list_support_requests()
    ]
    return {"requests": requests}
