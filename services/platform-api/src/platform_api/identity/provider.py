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


class ProviderError(Exception):
    """The provider could not do what was asked. The message never names a uid or an address."""


class IdentityProvider(Protocol):
    def verify_id_token(self, token: str) -> VerifiedIdentity:
        """Raises InvalidToken."""
        ...

    def create_session_cookie(self, id_token: str, ttl: timedelta) -> str: ...

    def verify_session_cookie(self, cookie: str) -> str:
        """Returns the uid; raises InvalidToken when bad, expired or revoked."""
        ...

    def revoke_sessions(self, uid: str) -> None: ...

    def delete_user(self, uid: str) -> None:
        """Delete the sign-in account. An account that is gone already counts as deleted.

        Raises ProviderError when the provider cannot.
        """
        ...


_TOKEN = "fake-token:"  # noqa: S105  (a test prefix, not a secret)
_COOKIE = "fake-session:"


class FakeIdentityProvider:
    """A provider for tests. Never used outside them.

    A token `fake-token:<name>` is accepted for a name in the address table and gives the name's
    current uid (`u-<name>` until it is deleted); `fake-token:<name>:<uid>` is a token of that
    account, refused once the account is deleted. Any other token raises InvalidToken. Names in
    `unverified` have an address that is not verified. A cookie is `fake-session:<uid>:<n>`,
    where n counts the cookies issued. The fake remembers each cookie it issued and, per uid,
    the count at the moment its sessions were revoked: it accepts only a cookie it issued, for a
    known uid, issued after the last revocation of that uid. A cookie issued here carries no
    expiry, so a cookie is never refused for its age (the real provider refuses expired
    cookies).

    `delete_user` records the uid in `deleted` and ends its sessions. As at the real
    provider, the next sign-in with the same address is a new account: the name then gives
    the uid `u-<name>-<k>`, and cookies of the deleted uid are refused.
    """

    def __init__(self, emails: Mapping[str, str], unverified: set[str] | None = None) -> None:
        self._emails = dict(emails)
        self.unverified: set[str] = set(unverified or ())
        self._issued: dict[str, tuple[str, int]] = {}  # cookie -> (uid, n)
        self._revoked_up_to: dict[str, int] = {}  # uid -> last n issued when revoked
        self._count = 0
        self._uids = {name: f"u-{name}" for name in self._emails}
        self.deleted: list[str] = []

    def verify_id_token(self, token: str) -> VerifiedIdentity:
        rest = token.removeprefix(_TOKEN) if token.startswith(_TOKEN) else None
        name, _, bound = (rest or "").partition(":")
        if rest is None or name not in self._emails or bound not in ("", self._uids[name]):
            raise InvalidToken("the sign-in token was refused")
        return VerifiedIdentity(
            uid=self._uids[name],
            email=self._emails[name],
            email_verified=name not in self.unverified,
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
        if uid not in self._uids.values() or n <= self._revoked_up_to.get(uid, 0):
            raise InvalidToken("the session was refused")
        return uid

    def revoke_sessions(self, uid: str) -> None:
        self._revoked_up_to[uid] = self._count

    def delete_user(self, uid: str) -> None:
        self.deleted.append(uid)
        self.revoke_sessions(uid)
        for name, held in self._uids.items():
            if held == uid:
                self._uids[name] = f"u-{name}-{len(self.deleted)}"
