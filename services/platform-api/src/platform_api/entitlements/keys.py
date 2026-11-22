"""The contact key port: a keyed hash that turns an address into an id."""

import hashlib
import hmac
from typing import Protocol


class ContactKey(Protocol):
    version: str

    def mac(self, data: bytes) -> bytes: ...


class LocalContactKey:
    def __init__(self, secret: bytes, version: str = "local") -> None:
        self._secret = secret
        self.version = version

    def mac(self, data: bytes) -> bytes:
        return hmac.new(self._secret, data, hashlib.sha256).digest()
