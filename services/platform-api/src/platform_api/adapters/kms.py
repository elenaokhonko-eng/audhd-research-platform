"""The contact key on Cloud KMS: an HMAC-SHA256 key whose material never leaves KMS."""

from typing import TYPE_CHECKING

import google_crc32c

if TYPE_CHECKING:
    from google.cloud import kms


def version_of(key_version_name: str) -> str:
    """The version of a key version's resource name: its last path segment."""
    head, sep, version = key_version_name.strip().rpartition("/cryptoKeyVersions/")
    if not sep or not head or not version or "/" in version:
        raise ValueError(
            "PLATFORM_CONTACT_KEY must be the resource name of a key version, ending in "
            "/cryptoKeyVersions/<n>"
        )
    return version


class KmsContactKey:
    """`mac` signs on KMS and checks that the answer is from this key and arrived whole."""

    def __init__(self, client: "kms.KeyManagementServiceClient", key_version_name: str) -> None:
        self.version = version_of(key_version_name)
        self._client = client
        self._name = key_version_name.strip()

    def mac(self, data: bytes) -> bytes:
        response = self._client.mac_sign(
            request={"name": self._name, "data": data, "data_crc32c": google_crc32c.value(data)}
        )
        mac = bytes(response.mac)
        if (
            response.name != self._name
            or response.verified_data_crc32c is not True
            or google_crc32c.value(mac) != response.mac_crc32c
        ):
            raise RuntimeError("the contact key gave an answer that failed its checks")
        return mac
