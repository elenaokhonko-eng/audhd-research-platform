"""Identity of the callers that present a Google token: Pub/Sub push and the owner."""

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PushIdentity:
    email: str


class NotAuthorised(Exception):
    def __init__(self, reason: Literal["invalid", "wrong_identity"]) -> None:
        super().__init__(reason)
        self.reason = reason


def _claims(token: str) -> dict[str, object]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("not a JWT")
        payload = parts[1]
        raw = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        claims = json.loads(raw)
    except (ValueError, binascii.Error) as exc:
        raise NotAuthorised("invalid") from exc
    if not isinstance(claims, dict):
        raise NotAuthorised("invalid")
    return claims


def push_identity_from_token(token: str, *, allowed_email: str) -> PushIdentity:
    """Read the caller's email from a Google-issued OIDC token and check it.

    The signature is deliberately NOT verified here. That is safe only because
    this service is deployed with Cloud Run IAM required (Terraform enforces
    it): Cloud Run itself verifies the token's signature, expiry and the
    invoker permission, and rejects the request before it reaches this code.
    Do not reuse this function on any service that is publicly invokable.
    What remains for us is to confirm which service account is calling.

    Raises NotAuthorised("invalid") if the token cannot be decoded or has no
    verified email, and NotAuthorised("wrong_identity") if the email is not
    the allowed one (an empty allowed_email never matches).
    """
    claims = _claims(token)
    email = claims.get("email")
    if not isinstance(email, str) or not email or claims.get("email_verified") is not True:
        raise NotAuthorised("invalid")
    if not allowed_email or email != allowed_email:
        raise NotAuthorised("wrong_identity")
    return PushIdentity(email=email)


GOOGLE_ISSUER = "https://accounts.google.com"


def google_account_from_token(token: str) -> str:
    """The Google account id (claim `sub`) of a person's identity token, signature checked.

    Cloud Run's own check is not enough for the owner's routes: any caller allowed to invoke
    the service could otherwise present a token it wrote itself. The signature and expiry are
    checked against Google's published keys. The audience is not checked: a token printed by
    `gcloud auth print-identity-token` for a person carries gcloud's own audience. The list of
    owner accounts is the gate.

    Raises NotAuthorised("invalid") for any token that fails; the cause is not repeated.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_token(token, google_requests.Request())
    except Exception:
        raise NotAuthorised("invalid") from None
    sub = claims.get("sub")
    if (
        claims.get("iss") != GOOGLE_ISSUER
        or claims.get("email_verified") is not True
        or not isinstance(sub, str)
        or not sub
    ):
        raise NotAuthorised("invalid")
    return sub
