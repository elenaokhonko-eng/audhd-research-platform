"""The cloud versions of the ports: Firestore, Cloud KMS and Identity Platform.

Only `main.py` and `cli.py` import this package; no feature module and no shared module does
(`.importlinter`). `configure_runtimes` builds every runtime once at start-up. Outside `local`
each cloud client is made on first use, so importing and `/health` need no credentials.
"""

import threading
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from google.cloud import firestore

    from platform_api.settings import Settings
    from platform_api.shared.bus import EventBus

T = TypeVar("T")


def in_transaction(client: "firestore.Client", work: "Callable[[firestore.Transaction], T]") -> T:
    """Run `work` in a Firestore transaction, retried on contention; `work` must be pure.

    A transaction that gives up after its retries is a RuntimeError: the library raises it as
    ValueError, which the routes would answer as a refusal (422) instead of a fault.
    """
    from google.cloud import firestore

    try:
        result: T = firestore.transactional(work)(client.transaction())
    except ValueError as exc:
        if str(exc).startswith(_GAVE_UP):
            raise RuntimeError("a Firestore transaction gave up after its retries") from exc
        raise
    return result


_GAVE_UP = "Failed to commit transaction"  # the start of the library's message


class Lazy:
    """Stands for an object that is built on first use, once, and then used for every call."""

    def __init__(self, build: Callable[[], object]) -> None:
        self._build = build
        self._built: object | None = None
        self._lock = threading.Lock()

    def __getattr__(self, name: str) -> Any:
        if self._built is None:
            with self._lock:
                if self._built is None:
                    self._built = self._build()
        return getattr(self._built, name)


_NO_KEY = (
    "PLATFORM_CONTACT_KEY is not set: it names the Cloud KMS key version that turns an "
    "address into a contact id"
)


class _MissingKey:
    """The contact key of a process started without one: any use says which setting is missing."""

    @property
    def version(self) -> str:
        raise RuntimeError(_NO_KEY)

    def mac(self, data: bytes) -> bytes:
        raise RuntimeError(_NO_KEY)


def configure_runtimes(settings: "Settings", bus: "EventBus", *, key_required: bool) -> None:
    """Set the runtimes of `entitlements`, `identity` and `library` for this process.

    In `local`: the in-memory stores and a local contact key. Elsewhere: Firestore, the
    Cloud KMS key named by PLATFORM_CONTACT_KEY, and Identity Platform. When the key is not
    set, `key_required` (the api service) stops the start with a message that names the
    setting; otherwise (hooks, jobs) the first use of the key raises that message. The
    identity provider is Identity
    Platform in every environment (in `local`, through its emulator when one is set).
    `request_refresh` and `last_reconcile_at` stay None until the Commerce lane wires them.
    """
    from functools import cache

    from platform_api.adapters.firebase import FirebaseIdentityProvider
    from platform_api.entitlements import runtime as entitlements_runtime
    from platform_api.entitlements.keys import ContactKey, LocalContactKey
    from platform_api.entitlements.store import EntitlementStore, InMemoryStore
    from platform_api.identity import runtime as identity_runtime
    from platform_api.identity.provider import IdentityProvider
    from platform_api.identity.store import InMemoryMemberStore, MemberStore
    from platform_api.library import runtime as library_runtime
    from platform_api.library.ports import (
        DownloadLog,
        FileStore,
        InMemoryDownloadLog,
        InMemoryFileStore,
        InMemoryItemStore,
        ItemStore,
    )
    from platform_api.library.settings import LibrarySettings
    from platform_api.shared.ratelimit import InMemoryRateLimiter, RateLimiter

    store: EntitlementStore
    key: ContactKey
    members: MemberStore
    limiter: RateLimiter
    library: library_runtime.Runtime
    if settings.env == "local":
        store, members, limiter = InMemoryStore(), InMemoryMemberStore(), InMemoryRateLimiter()
        key = LocalContactKey(b"local-only")
        library = library_runtime.Runtime(
            items=InMemoryItemStore(),
            staging=InMemoryFileStore(),
            files=InMemoryFileStore(),
            downloads=InMemoryDownloadLog(),
            bus=bus,
        )
    else:
        key_name = settings.contact_key.strip()
        if not key_name and key_required:
            raise RuntimeError(_NO_KEY + ", and this service cannot start without it.")
        from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
        from platform_api.adapters.firestore_members import FirestoreMemberStore
        from platform_api.adapters.firestore_ratelimit import FirestoreRateLimiter
        from platform_api.adapters.kms import KmsContactKey, version_of
        from platform_api.library.adapters import (
            BucketFileStore,
            FirestoreDownloadLog,
            FirestoreItemStore,
        )

        if key_name:
            version_of(key_name)  # a name that is not a key version stops the start here

        @cache
        def client() -> "firestore.Client":
            from google.cloud import firestore

            return firestore.Client(project=settings.gcp_project)

        def kms_key() -> KmsContactKey:
            from google.cloud import kms

            return KmsContactKey(kms.KeyManagementServiceClient(), key_name)

        store = cast(EntitlementStore, Lazy(lambda: FirestoreEntitlementStore(client())))
        members = cast(MemberStore, Lazy(lambda: FirestoreMemberStore(client())))
        limiter = cast(RateLimiter, Lazy(lambda: FirestoreRateLimiter(client())))
        key = (
            cast(ContactKey, _KeyWithVersion(version_of(key_name), Lazy(kms_key)))
            if key_name
            else cast(ContactKey, _MissingKey())
        )
        lib_settings = LibrarySettings()
        library = library_runtime.Runtime(
            items=cast(ItemStore, Lazy(lambda: FirestoreItemStore(client()))),
            staging=cast(
                FileStore,
                Lazy(
                    lambda: BucketFileStore.from_default_credentials(
                        lib_settings.library_staging_bucket
                    )
                ),
            ),
            files=cast(
                FileStore,
                Lazy(lambda: BucketFileStore.from_default_credentials(lib_settings.library_bucket)),
            ),
            downloads=cast(DownloadLog, Lazy(lambda: FirestoreDownloadLog(client()))),
            bus=bus,
        )

    def provider() -> FirebaseIdentityProvider:
        import firebase_admin  # type: ignore[import-untyped]

        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = firebase_admin.initialize_app(options={"projectId": settings.gcp_project})
        return FirebaseIdentityProvider(app)

    entitlements_runtime.set_runtime(entitlements_runtime.Runtime(store, key, bus))
    library_runtime.set_runtime(library)
    identity_runtime.set_runtime(
        identity_runtime.Runtime(
            members=members,
            provider=cast(IdentityProvider, Lazy(provider)),
            bus=bus,
            session_ttl=timedelta(days=settings.session_ttl_days),
            limiter=limiter,
            request_refresh=None,
            last_reconcile_at=None,
        )
    )


class _KeyWithVersion:
    """The contact key's version is known from its name, without a client."""

    def __init__(self, version: str, key: Any) -> None:
        self.version = version
        self._key = key

    def mac(self, data: bytes) -> bytes:
        mac: bytes = self._key.mac(data)
        return mac
