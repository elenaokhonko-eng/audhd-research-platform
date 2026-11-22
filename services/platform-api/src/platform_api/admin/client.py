"""The owner's routes, as `platform-cli` calls them.

An address goes only in a POST body, never in a URL. Every call carries the owner's Google
identity token.
"""

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx


class AdminError(Exception):
    """A non-2xx answer: the status, and the contract's error code and message."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _error_from(response: httpx.Response) -> AdminError:
    try:
        error = response.json()["error"]
        code, message = error["code"], error["message"]
        if isinstance(code, str) and isinstance(message, str):
            return AdminError(response.status_code, code, message)
    except (ValueError, KeyError, TypeError):
        pass
    return AdminError(
        response.status_code, "unknown", f"The service answered {response.status_code}."
    )


class AdminClient:
    def __init__(
        self, base_url: str, token: Callable[[], str], http: httpx.Client | None = None
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._http = http if http is not None else httpx.Client(timeout=60.0)

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self._token()}"}
        content = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            content = json.dumps(body, separators=(",", ":"))
        response = self._http.request(method, self._base + path, headers=headers, content=content)
        if not response.is_success:
            raise _error_from(response)
        try:
            return response.json()
        except ValueError:
            raise AdminError(
                response.status_code, "unknown", "The service's answer was not readable."
            ) from None

    def contact_show(self, email: str) -> dict[str, Any] | None:
        found: dict[str, Any] | None = self._call(
            "POST", "/v1/admin/contacts/search", {"email": email}
        )["contact"]
        return found

    def grant_create(
        self,
        email: str,
        grant: str,
        reason: str,
        *,
        months: int | None = None,
        valid_until: str | None = None,
    ) -> str:
        body: dict[str, Any] = {"email": email, "grant": grant, "reason": reason}
        if months is not None:
            body["months"] = months
        if valid_until is not None:
            body["valid_until"] = valid_until
        return str(self._call("POST", "/v1/admin/entitlements", body)["entitlement_id"])

    def grant_revoke(self, entitlement_id: str, reason: str) -> None:
        path = f"/v1/admin/entitlements/{quote(entitlement_id, safe='')}/revoke"
        self._call("POST", path, {"reason": reason})

    def campaign_apply(self, campaigns: list[dict[str, Any]]) -> int:
        return int(self._call("PUT", "/v1/admin/campaigns", {"campaigns": campaigns})["written"])

    def launch_set(self, switches: dict[str, Any]) -> dict[str, Any]:
        stored: dict[str, Any] = self._call("PUT", "/v1/admin/launch", switches)
        return stored

    def launch_report(self) -> dict[str, Any]:
        report: dict[str, Any] = self._call("GET", "/v1/admin/launch/report")
        return report

    def support_list(self) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = self._call("GET", "/v1/admin/support-requests")["requests"]
        return requests
