"""Identity Platform through the Firebase Admin SDK: sign-in tokens and session cookies.

Each call goes through the module `firebase_admin.auth` at call time, so a test can replace
a function there. Every refusal becomes `InvalidToken` with a fixed message: the SDK's own
messages can repeat the token or an address, and they are dropped (`from None`).
"""

from datetime import timedelta
from typing import Any

from firebase_admin import auth  # type: ignore[import-untyped]
from firebase_admin import exceptions as firebase_exceptions

from platform_api.identity.provider import InvalidToken, VerifiedIdentity

_REFUSED = (firebase_exceptions.FirebaseError, ValueError)


class FirebaseIdentityProvider:
    def __init__(self, app: Any) -> None:
        self._app = app

    def verify_id_token(self, token: str) -> VerifiedIdentity:
        try:
            claims = auth.verify_id_token(token, app=self._app, check_revoked=True)
        except _REFUSED:
            raise InvalidToken("the sign-in token was refused") from None
        uid, email = claims.get("uid"), claims.get("email")
        if not isinstance(uid, str) or not uid or not isinstance(email, str) or not email:
            raise InvalidToken("the sign-in token was refused")
        return VerifiedIdentity(
            uid=uid, email=email, email_verified=claims.get("email_verified") is True
        )

    def create_session_cookie(self, id_token: str, ttl: timedelta) -> str:
        try:
            cookie = auth.create_session_cookie(id_token, expires_in=ttl, app=self._app)
        except _REFUSED:
            raise InvalidToken("the session could not be created") from None
        return cookie.decode() if isinstance(cookie, bytes) else str(cookie)

    def verify_session_cookie(self, cookie: str) -> str:
        try:
            claims = auth.verify_session_cookie(cookie, check_revoked=True, app=self._app)
        except _REFUSED:
            raise InvalidToken("the session was refused") from None
        uid = claims.get("uid")
        if not isinstance(uid, str) or not uid:
            raise InvalidToken("the session was refused")
        return uid

    def revoke_sessions(self, uid: str) -> None:
        try:
            auth.revoke_refresh_tokens(uid, app=self._app)
        except _REFUSED:
            raise InvalidToken("the sessions could not be ended") from None
