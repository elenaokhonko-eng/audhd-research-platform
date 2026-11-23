from datetime import timedelta

from platform_api.library.adapters import BucketFileStore
from tests.fixtures.people import T0


class FakeBlob:
    def __init__(self, name, log):
        self.name, self.log = name, log

    def generate_signed_url(self, **kwargs):
        self.log.append(kwargs)
        return f"https://storage.example/{self.name}?sig"


class FakeBucket:
    def __init__(self):
        self.log = []

    def blob(self, name):
        return FakeBlob(name, self.log)


def test_a_link_is_signed_for_get_for_the_given_time_without_a_key_file():
    bucket = FakeBucket()
    store = BucketFileStore(bucket, signer="svc@example.org", token=lambda: "tok")
    url = store.signed_url("items/sample-map/1.0/f.pdf", timedelta(seconds=600), T0)
    [call] = bucket.log
    assert url.startswith("https://storage.example/items/sample-map/1.0/f.pdf")
    assert (call["version"], call["method"], call["expiration"]) == (
        "v4",
        "GET",
        timedelta(seconds=600),
    )
    assert (call["service_account_email"], call["access_token"]) == (
        "svc@example.org",
        "tok",
    )


class CopyingBucket(FakeBucket):
    def __init__(self, fail=False):
        super().__init__()
        self.fail, self.copies = fail, []

    def copy_blob(self, blob, destination_bucket, new_name, **kwargs):
        self.copies.append((blob.name, new_name, kwargs))
        if self.fail:
            from google.api_core.exceptions import PreconditionFailed

            raise PreconditionFailed("exists")


def test_a_copy_never_overwrites():
    staging, target = CopyingBucket(), CopyingBucket()
    files = BucketFileStore(target, signer="s", token=lambda: "t")
    assert (
        files.create_from(
            BucketFileStore(staging, signer="s", token=lambda: "t"),
            "batch-1/a/f.pdf",
            "items/a/1.0/f.pdf",
        )
        is True
    )
    assert staging.copies == [("batch-1/a/f.pdf", "items/a/1.0/f.pdf", {"if_generation_match": 0})]
    refusing = CopyingBucket(fail=True)
    assert (
        files.create_from(BucketFileStore(refusing, signer="s", token=lambda: "t"), "x", "y")
        is False
    )


def test_importing_the_adapters_creates_no_client(monkeypatch):
    import importlib

    from google.cloud import firestore, storage

    def boom(*a, **k):
        raise AssertionError("a client was created at import")

    monkeypatch.setattr(storage, "Client", boom)
    monkeypatch.setattr(firestore, "Client", boom)
    import platform_api.library.adapters as adapters

    importlib.reload(adapters)


def test_a_download_record_carries_its_lifetime_and_no_address():
    from platform_api.library.adapters import FirestoreDownloadLog
    from tests.fake_firestore import FakeFirestore

    db = FakeFirestore()
    log = FirestoreDownloadLog(db)
    log.add("u-ana", "sample-map", "1.0", T0 + timedelta(minutes=5))
    log.add("u-ana", "sample-map", "1.0", T0)
    log.add("u-bo", "sample-map", "1.0", T0)
    [first, *_] = [d for (c, _), d in sorted(db.docs.items()) if c == "downloads"]
    assert first == {
        "member_uid": "u-ana",
        "sku": "sample-map",
        "version": "1.0",
        "at": T0 + timedelta(minutes=5),
        "expires_at": T0 + timedelta(minutes=5) + timedelta(days=365),
    }
    # The fake does not apply the `at >` filter; Firestore and the emulator do.
    assert log.times_since("u-ana", T0 - timedelta(hours=1)) == [T0, T0 + timedelta(minutes=5)]


def test_an_item_record_is_stored_under_its_sku(lib):
    from platform_api.library.adapters import FirestoreItemStore
    from tests.fake_firestore import FakeFirestore
    from tests.library.test_catalogue import shelf

    shelf(lib)
    db = FakeFirestore()
    items = FirestoreItemStore(db)
    for item in lib.items.list_all():
        items.put(item)
    assert items.get("sample-map") == lib.items.get("sample-map")
    assert items.get("nope") is None
    assert [i.sku for i in items.list_all()] == [i.sku for i in lib.items.list_all()]
    assert ("library_items", "sample-map") in db.docs


def test_a_copy_works_from_a_store_built_on_first_use():
    class OnFirstUse:  # as Core's Lazy: attributes are forwarded to the built store
        def __init__(self, store):
            self._store = store

        def __getattr__(self, name):
            return getattr(self._store, name)

    staging, target = CopyingBucket(), CopyingBucket()
    files = BucketFileStore(target, signer="s", token=lambda: "t")
    source = OnFirstUse(BucketFileStore(staging, signer="s", token=lambda: "t"))
    assert files.create_from(source, "batch-1/a/f.pdf", "items/a/1.0/f.pdf") is True
    assert [c[:2] for c in staging.copies] == [("batch-1/a/f.pdf", "items/a/1.0/f.pdf")]
