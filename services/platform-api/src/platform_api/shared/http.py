"""The error body of contracts section 1, for every error the service itself raises."""

import logging
import traceback
from http import HTTPStatus
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_log = logging.getLogger(__name__)

_CODES = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    422: "validation_failed",
    429: "rate_limited",
    503: "unavailable",
}


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        retry_after: int | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after
        self.reason = reason


def _body(
    code: str, message: str, retry_after: int | None = None, reason: str | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "retry_after": retry_after}
    if reason is not None:
        error["reason"] = reason
    return {"error": error}


def _field(loc: tuple[Any, ...]) -> str:
    # A location can carry a dictionary key the caller chose; never repeat an address.
    return ".".join("*" if "@" in str(part) else str(part) for part in loc)


def _where(exc: BaseException) -> str:
    """The exception's type and the frames it passed through; never its message."""
    frames = traceback.extract_tb(exc.__traceback__)
    path = " < ".join(f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} {f.name}" for f in frames[::-1])
    return f"{type(exc).__name__} at {path}"


class _CatchAll:
    """Answers an unhandled exception with the contract's 500, and does not re-raise it.

    Starlette's ServerErrorMiddleware re-raises after its handler, and the server then logs the
    traceback with the exception's message, which may hold an address. Here only the type and
    the frames are logged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            _log.error("unhandled error: %s", _where(exc))
            if not started:
                response = JSONResponse(
                    _body("internal_error", "Something went wrong on our side."), status_code=500
                )
                await response(scope, receive, send)


def install_error_handlers(app: FastAPI) -> None:
    async def api_error(request: Request, exc: Exception) -> JSONResponse:
        exc = cast(ApiError, exc)
        return JSONResponse(
            _body(exc.code, exc.message, exc.retry_after, exc.reason), status_code=exc.status
        )

    async def validation(request: Request, exc: Exception) -> JSONResponse:
        exc = cast(RequestValidationError, exc)
        fields = sorted({_field(tuple(e["loc"])) for e in exc.errors()})
        message = "These fields are missing or not valid: " + ", ".join(fields) + "."
        return JSONResponse(_body("validation_failed", message), status_code=422)

    async def http_error(request: Request, exc: Exception) -> JSONResponse:
        exc = cast(StarletteHTTPException, exc)
        status = exc.status_code
        try:
            phrase = HTTPStatus(status).phrase
        except ValueError:
            phrase = "error"
        code = _CODES.get(status) or phrase.lower().replace(" ", "_").replace("-", "_")
        return JSONResponse(
            _body(code, phrase + "."), status_code=status, headers=getattr(exc, "headers", None)
        )

    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            _body("internal_error", "Something went wrong on our side."), status_code=500
        )

    app.add_exception_handler(ApiError, api_error)
    app.add_exception_handler(RequestValidationError, validation)
    app.add_exception_handler(StarletteHTTPException, http_error)
    app.add_exception_handler(Exception, unhandled)
    app.add_middleware(_CatchAll)


def current_member(
    request: Request,
    session: Annotated[str | None, Header(alias="X-Member-Session")] = None,
) -> Any:
    """The member of the forwarded session, or 401. Refusal is anything the lookup refuses.

    `shared` may not import `identity`, so the lookup is `app.state.member_from_session`,
    which `create_app` sets. It returns a member reference (`uid`, `terms_ok`) and raises a
    PermissionError when the session is not valid; any other error is a fault, not a refusal.
    """
    lookup = getattr(request.app.state, "member_from_session", None)
    if not session or lookup is None:
        raise ApiError(401, "unauthenticated", "Please sign in.")
    try:
        return lookup(session)
    except PermissionError:
        raise ApiError(401, "unauthenticated", "Please sign in.") from None


def member_with_terms(member: Annotated[Any, Depends(current_member)]) -> Any:
    """As `current_member`, then 409 until the member has accepted the current terms."""
    if not getattr(member, "terms_ok", False):
        raise ApiError(
            409, "terms_required", "Please accept the current terms and privacy notice first."
        )
    return member
