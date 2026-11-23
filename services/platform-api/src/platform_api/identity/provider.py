"""The identity provider port: verifies sign-in tokens and issues session cookies."""

from collections.abc import Mapping
from datetime import timedelta
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class VerifiedIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    uid: str
    email: str = Field(repr=False)
    email_verified: bool


class InvalidToken(Exception):
    """A token or cookie was refused. The message never repeats the token or an address."""


class IdentityProvider(Protocol):
    def verify_id_token(self, token: str) -> VerifiedIdentity:
        """Raises InvalidToken."""
        ...

    def create_session_cookie(self, id_token: str, ttl: timedelta) -> str: ...

    def verify_session_cookie(self, cookie: str) -> str:
        """Returns the uid; raises InvalidToken when bad, expired or revoked."""
        ...

    def revoke_sessions(self, uid: str) -> None: ...


_TOKEN = "fake-token:"  # noqa: S105  (a test prefix, not a secret)
_COOKIE = "fake-session:"


class FakeIdentityProvider:
    """A provider for tests. Never used outside them.

    A token `fake-token:<name>` is accepted for a name in the address table and gives the
    uid `u-<name>`; any other token raises InvalidToken. Names in `unverified` have an
    address that is not verified. A cookie is `fake-session:<uid>:<n>`, where n counts the
    cookies issued. The fake remembers each cookie it issued and, per uid, the count at the
    moment its sessions were revoked: it accepts only a cookie it issued, for a known uid,
    issued after the last revocation of that uid. A cookie issued here carries no expiry,
    so a cookie is never refused for its age (the real provider refuses expired cookies).
    """

    def __init__(self, emails: Mapping[str, str], unverified: set[str] | None = None) -> None:
        self._emails = dict(emails)
        self.unverified: set[str] = set(unverified or ())
        self._issued: dict[str, tuple[str, int]] = {}  # cookie -> (uid, n)
        self._revoked_up_to: dict[str, int] = {}  # uid -> last n issued when revoked
        self._count = 0

    def verify_id_token(self, token: str) -> VerifiedIdentity:
        name = token.removeprefix(_TOKEN) if token.startswith(_TOKEN) else None
        if name is None or name not in self._emails:
            raise InvalidToken("the sign-in token was refused")
        return VerifiedIdentity(
            uid=f"u-{name}", email=self._emails[name], email_verified=name not in self.unverified
        )

    def create_session_cookie(self, id_token: str, ttl: timedelta) -> str:
        uid = self.verify_id_token(id_token).uid
        self._count += 1
        cookie = f"{_COOKIE}{uid}:{self._count}"
        self._issued[cookie] = (uid, self._count)
        return cookie

    def verify_session_cookie(self, cookie: str) -> str:
        found = self._issued.get(cookie)
        if found is None:
            raise InvalidToken("the session was refused")
        uid, n = found
        known = {f"u-{name}" for name in self._emails}
        if uid not in known or n <= self._revoked_up_to.get(uid, 0):
            raise InvalidToken("the session was refused")
        return uid

    def revoke_sessions(self, uid: str) -> None:
        self._revoked_up_to[uid] = self._count
