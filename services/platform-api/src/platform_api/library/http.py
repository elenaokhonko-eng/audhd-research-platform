"""The library's routes: the member's shelf, one item and a download link; the owner's publish.

While the switch `library_open` is off, the three member routes answer 404 before anything is
looked up. A sku in the address that is not a sku answers 404 the same way; the handler checks
it, because a pattern on the path parameter would answer 422.
"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError
from starlette.concurrency import run_in_threadpool

from platform_api.admin.public import owner
from platform_api.entitlements import public as entitlements
from platform_api.library.models import SKU, PublishReport
from platform_api.library.publishing import STAGING_PREFIX, publish
from platform_api.library.reading import (
    ItemNotFound,
    NotEntitled,
    TooManyDownloads,
    catalogue,
    download_link,
    item,
)
from platform_api.shared import clock
from platform_api.shared.http import ApiError, member_with_terms

router = APIRouter()
hooks_router = APIRouter()

Member = Annotated[Any, Depends(member_with_terms)]
Owner = Annotated[str, Depends(owner)]


class PublishBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staging_prefix: str
    dry_run: StrictBool


def _not_found() -> ApiError:
    return ApiError(404, "not_found", "There is no such item.")


def _open() -> None:
    if not entitlements.launch_config().library_open:
        raise ApiError(404, "not_found", "The library is not open yet.")


def _checked(sku: str) -> str:
    if not SKU.fullmatch(sku):
        raise _not_found()
    return sku


@router.get("/v1/library/items")
def list_items(member: Member) -> dict[str, Any]:
    _open()
    access = entitlements.access_for(member.uid, clock.utcnow())
    return {"items": [card.model_dump(mode="json") for card in catalogue(access)]}


@router.get("/v1/library/items/{sku}")
def get_item(sku: str, member: Member) -> dict[str, Any]:
    _open()
    _checked(sku)
    access = entitlements.access_for(member.uid, clock.utcnow())
    try:
        detail = item(sku, access)
    except ItemNotFound:
        raise _not_found() from None
    return detail.model_dump(mode="json")


@router.post("/v1/library/items/{sku}/download")
def download(sku: str, member: Member) -> dict[str, Any]:
    _open()
    _checked(sku)
    try:
        link = download_link(member.uid, sku, clock.utcnow())
    except ItemNotFound:
        raise _not_found() from None
    except NotEntitled as refused:
        raise ApiError(
            403, "forbidden", "Your membership does not open this item.", reason=refused.reason
        ) from None
    except TooManyDownloads as limited:
        raise ApiError(
            429,
            "rate_limited",
            "Too many downloads in the last hour. Please try again later.",
            retry_after=limited.retry_after,
        ) from None
    return link.model_dump(mode="json")


@router.post("/v1/admin/library/publish")
async def publish_items(request: Request, account: Owner) -> PublishReport:
    """Publishes, or with `dry_run` only checks, the item folders under `staging_prefix`.

    Every call by the owner leaves one audit entry, a malformed body included: the body is read
    and validated here, inside the audited block, not by FastAPI before the handler runs. The
    action is `library.dry_run` when the body asked for a dry run, else `library.published`.
    """
    now = clock.utcnow()
    status = 500
    dry_run = False
    staging_prefix: str | None = None
    try:
        try:
            raw: Any = json.loads(await request.body())
        except ValueError:
            raw = None
        if isinstance(raw, dict):
            dry_run = raw.get("dry_run") is True
            named = raw.get("staging_prefix")
            staging_prefix = named if isinstance(named, str) else None
        try:
            body = PublishBody.model_validate(raw)
        except ValidationError as invalid:
            status = 422
            raise _invalid_body(invalid) from None
        # Checked here with publish's own pattern, so that no other ValueError reads as a 422.
        if not STAGING_PREFIX.fullmatch(body.staging_prefix):
            status = 422
            raise ApiError(
                422,
                "validation_failed",
                "staging_prefix: use 1 to 40 lower-case letters, digits and hyphens.",
            )
        report = await run_in_threadpool(
            publish, body.staging_prefix, body.dry_run, f"owner:{account}", now
        )
        status = 200
        return report
    finally:
        evidence = {"route": "library/publish", "outcome": str(status)}
        if staging_prefix is not None:
            evidence["staging_prefix"] = staging_prefix
        entry = entitlements.AuditEntry(
            at=now,
            actor=f"owner:{account}",
            action="library.dry_run" if dry_run else "library.published",
            subject="admin",
            reason=None,
            evidence=evidence,
        )
        await run_in_threadpool(entitlements.write_audit, entry)


def _invalid_body(invalid: ValidationError) -> ApiError:
    """Names the fields, never their values (as shared.http's handler does)."""
    fields = sorted(
        {
            ".".join("*" if "@" in str(p) else str(p) for p in e["loc"]) or "body"
            for e in invalid.errors()
        }
    )
    return ApiError(
        422,
        "validation_failed",
        "These fields are missing or not valid: " + ", ".join(fields) + ".",
    )
