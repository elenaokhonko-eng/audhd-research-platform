"""The error body of contracts section 1, for every error the service itself raises."""

from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_CODES = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
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
