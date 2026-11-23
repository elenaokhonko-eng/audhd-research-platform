from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Self

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, model_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from platform_api.admin.public import owner
from platform_api.commerce.models import Promotion
from platform_api.commerce.ports import JobStartError
from platform_api.commerce.promotions import active_promotions, put_promotions, upgrade_options
from platform_api.commerce.refresh import RateLimited, request_refresh
from platform_api.commerce.runtime import get_runtime
from platform_api.entitlements import public as entitlements
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


@router.get("/v1/public/promotions/active")
def public_promotions(response: Response) -> dict[str, Any]:
    """For the `guests` audience. No member session; cacheable for a minute."""
    response.headers["Cache-Control"] = "public, max-age=60"
    views = active_promotions("guests", clock.utcnow())
    return {"promotions": [v.model_dump(mode="json") for v in views]}


@router.get("/v1/me/upgrade-options")
def me_upgrade_options(member: Termed) -> dict[str, Any]:
    return upgrade_options(member.uid, clock.utcnow()).model_dump(mode="json")


# The owner's routes. As Core's admin routes: (method, path) -> (route name, audit action).
AUDIT_ACTIONS: dict[tuple[str, str], tuple[str, str]] = {
    ("PUT", "/v1/admin/promotions"): ("promotions", "promotions.written"),
    ("GET", "/v1/admin/promotions"): ("promotions", "admin.read"),
}


# `_status_of` and `_AuditedRoute` mirror `_status_of` and `AuditedRoute` in
# `platform_api/admin/http.py`, which is not public. They must change together: same actor,
# subject, evidence and outcome, one entry per call by a verified owner.
def _status_of(exc: Exception) -> int:
    if isinstance(exc, ApiError):
        return exc.status
    if isinstance(exc, RequestValidationError):
        return 422
    if isinstance(exc, StarletteHTTPException):
        return exc.status_code
    return 500


class _AuditedRoute(APIRoute):
    """One audit entry after every call by a verified owner, refusals and reads included,
    in the form Core's admin routes write it. A caller `owner` refused is not audited."""

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
                        subject="admin",
                        reason=None,
                        evidence={"route": route, "outcome": str(status)},
                    )
                    await run_in_threadpool(entitlements.write_audit, entry)

        return audited


admin_router = APIRouter(dependencies=[Depends(owner)], route_class=_AuditedRoute)

Owner = Annotated[str, Depends(owner)]  # resolved once per request, with the router's


class PromotionsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    promotions: list[Promotion]

    @model_validator(mode="after")
    def _ids_once(self) -> Self:
        ids = [p.id for p in self.promotions]
        if len(set(ids)) != len(ids):
            raise ValueError("an id is named more than once")
        return self


@admin_router.put("/v1/admin/promotions")
def put_admin_promotions(body: PromotionsBody, account: Owner) -> dict[str, int]:
    """Each id once, each window ending after it starts, each Substack link on https."""
    try:
        written = put_promotions(body.promotions, f"owner:{account}")
    except ValueError:
        raise ApiError(422, "validation_failed", "Name each promotion id once.") from None
    return {"written": written}


@admin_router.get("/v1/admin/promotions")
def get_admin_promotions() -> dict[str, Any]:
    promotions = sorted(get_runtime().promotions.list(), key=lambda p: (p.starts_at, p.id))
    return {
        "promotions": [
            p.model_dump(mode="json", include={"id", "channel", "starts_at", "ends_at", "counts"})
            for p in promotions
        ]
    }


router.include_router(admin_router)
