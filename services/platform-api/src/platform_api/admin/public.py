"""The owner's gate. Every `/v1/admin/` router depends on `owner`, which this module offers."""

import logging
from typing import Annotated

from fastapi import Header, Request

from platform_api.shared.http import ApiError

__all__ = ["owner"]

_log = logging.getLogger(__name__)


def _refused() -> ApiError:
    # One answer for every cause: the caller does not learn which check failed.
    return ApiError(403, "forbidden", "Not allowed.")


def owner(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """The account id of the owner calling, or 403.

    Reads `Authorization: Bearer <token>`, asks `app.state.verify_owner` for the Google account
    id in the token, and accepts only an id in `settings.owner_accounts`. No verifier, or an
    empty list, lets nobody in. Neither the token nor the account id is logged.
    """
    verify = getattr(request.app.state, "verify_owner", None)
    scheme, _, token = (authorization or "").partition(" ")
    token = token.strip()
    if verify is None or scheme.lower() != "bearer" or not token:
        _log.warning("an admin request was refused")
        raise _refused()
    try:
        account = verify(token)
    except Exception:
        _log.warning("an admin request was refused")
        raise _refused() from None
    if not isinstance(account, str) or account not in request.app.state.settings.owner_accounts:
        _log.warning("an admin request was refused")
        raise _refused()
    request.state.owner_account = account  # read by the audit of the admin routes
    return account
