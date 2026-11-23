"""The cloud versions of the library's ports: Firestore records and Cloud Storage files.

Only Core's `platform_api/adapters` imports this module (it builds the library runtime); no
library code does. Every Google client library is imported inside the function that uses it,
so importing this module creates no client and needs no credentials.

Links are signed without a key file: `generate_signed_url` is given the service account's
address and an access token and signs through the IAM Credentials API. The account needs the
role Service Account Token Creator on itself, and that API must be enabled.
"""

import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from platform_api.library.models import LibraryItem
from platform_api.library.ports import FileStore

if TYPE_CHECKING:
    import google.cloud.storage as storage  # type: ignore[import-untyped]  # ships no types
    from google.cloud import firestore

DOWNLOAD_LIFETIME = timedelta(days=365)  # a download's `expires_at` is its `at` plus this


class FirestoreItemStore:
    """`library_items/{sku}`."""

    def __init__(self, client: "firestore.Client") -> None:
        self._items = client.collection("library_items")

    def get(self, sku: str) -> LibraryItem | None:
        snapshot = self._items.document(sku).get()
        return LibraryItem.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def list_all(self) -> list[LibraryItem]:
        """In order of sku."""
        query = self._items.order_by("sku")
        return [LibraryItem.model_validate(s.to_dict()) for s in query.stream()]

    def put(self, item: LibraryItem) -> None:
        self._items.document(item.sku).set(item.model_dump())


class FirestoreDownloadLog:
    """`downloads/{auto}`: `member_uid`, `sku`, `version`, `at`, and `expires_at` for
    Firestore's time-to-live policy. `times_since` needs the index (`member_uid`, `at`)."""

    def __init__(self, client: "firestore.Client") -> None:
        self._downloads = client.collection("downloads")

    def add(self, member_uid: str, sku: str, version: str, at: datetime) -> None:
        self._downloads.document().set(
            {
                "member_uid": member_uid,
                "sku": sku,
                "version": version,
                "at": at,
                "expires_at": at + DOWNLOAD_LIFETIME,
            }
        )

    def times_since(self, member_uid: str, since: datetime) -> list[datetime]:
        """The member's downloads with `at > since`, oldest first."""
        from google.cloud.firestore import FieldFilter

        query = (
            self._downloads.where(filter=FieldFilter("member_uid", "==", member_uid))
            .where(filter=FieldFilter("at", ">", since))
            .order_by("at")
        )
        found: list[datetime] = []
        for snapshot in query.stream():
            data = snapshot.to_dict() or {}
            found.append(data["at"])
        return found


class BucketFileStore:
    """The files of one bucket. `signer` and `token` are used only to sign links."""

    def __init__(self, bucket: "storage.Bucket", signer: str, token: Callable[[], str]) -> None:
        self._bucket = bucket
        self._signer = signer
        self._token = token

    @property
    def bucket(self) -> "storage.Bucket":
        return self._bucket

    @classmethod
    def from_default_credentials(cls, bucket_name: str) -> "BucketFileStore":
        """The bucket through the service's own credentials, which also sign the links.

        The credentials are refreshed once here, because on Cloud Run the account's address is
        known only after a refresh; afterwards `token` refreshes them when they have expired.
        """
        import google.auth
        import google.cloud.storage as storage
        from google.auth.transport.requests import Request

        credentials: Any
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        lock = threading.Lock()

        def token() -> str:
            with lock:
                if not credentials.valid:
                    credentials.refresh(Request())
                return str(credentials.token)

        token()
        signer = str(credentials.service_account_email)
        client = storage.Client(project=project, credentials=credentials)
        return cls(client.bucket(bucket_name), signer=signer, token=token)

    def list_dirs(self, prefix: str) -> list[str]:
        """The folder names directly under `prefix + "/"`."""
        start = prefix + "/"
        blobs: Any = self._bucket.list_blobs(prefix=start, delimiter="/")
        for _ in blobs:  # the folder names are known once every page has been read
            pass
        return sorted(p[len(start) :].rstrip("/") for p in blobs.prefixes)

    def read(self, path: str) -> bytes | None:
        from google.api_core.exceptions import NotFound

        try:
            data: bytes = self._bucket.blob(path).download_as_bytes()
        except NotFound:
            return None
        return data

    def exists(self, path: str) -> bool:
        return bool(self._bucket.blob(path).exists())

    def sha256(self, path: str) -> str | None:
        """Cloud Storage keeps no SHA-256, so the file is read and hashed."""
        import hashlib

        data = self.read(path)
        return hashlib.sha256(data).hexdigest() if data is not None else None

    def create_from(self, source: FileStore, src: str, dst: str) -> bool:
        """Copy `src` of `source` to `dst` only if `dst` does not exist; say whether it did."""
        from google.api_core.exceptions import PreconditionFailed

        # Read as an attribute, not by isinstance, so a store built on first use still copies.
        source_bucket = getattr(source, "bucket", None)
        if source_bucket is None:
            raise TypeError("a bucket copies only from another bucket")
        try:
            source_bucket.copy_blob(
                source_bucket.blob(src), self._bucket, dst, if_generation_match=0
            )
        except PreconditionFailed:
            return False
        return True

    def signed_url(self, path: str, ttl: timedelta, now: datetime) -> str:
        """A version-4 link for GET that lasts `ttl`. Cloud Storage counts it from the moment
        of signing, which is `now` within the time of one call."""
        url: str = self._bucket.blob(path).generate_signed_url(
            version="v4",
            method="GET",
            expiration=ttl,
            service_account_email=self._signer,
            access_token=self._token(),
        )
        return url
