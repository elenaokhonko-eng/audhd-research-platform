import pytest

from platform_api.adapters.firebase import FirebaseIdentityProvider
from platform_api.adapters.kms import KmsContactKey
from platform_api.identity.provider import InvalidToken


class FakeKms:
    def __init__(self, name=None, crc_ok=True):
        self.name, self.crc_ok = name, crc_ok

    def mac_sign(self, request):
        import google_crc32c

        mac = b"m" * 32
        crc = google_crc32c.value(mac) if self.crc_ok else 1
        return type(
            "R",
            (),
            {
                "name": self.name or request["name"],
                "mac": mac,
                "mac_crc32c": crc,
                "verified_data_crc32c": True,
            },
        )()


NAME = "projects/p/locations/l/keyRings/platform/cryptoKeys/contact-id/cryptoKeyVersions/1"


def test_the_key_reports_its_version_and_checks_the_answer():
    assert (
        KmsContactKey(FakeKms(), NAME).version == "1"
        and KmsContactKey(FakeKms(), NAME).mac(b"x") == b"m" * 32
    )
    for broken in (FakeKms(name="other"), FakeKms(crc_ok=False)):
        with pytest.raises(RuntimeError, match="contact key"):
            KmsContactKey(broken, NAME).mac(b"x")


def test_a_provider_error_becomes_invalid_token_without_the_token(monkeypatch):
    import firebase_admin.auth as fa

    def boom(*a, **k):
        raise fa.InvalidIdTokenError("bad token eyJhbGciOi for ana@example.org")

    monkeypatch.setattr(fa, "verify_id_token", boom)
    with pytest.raises(InvalidToken) as err:
        FirebaseIdentityProvider(app=None).verify_id_token("eyJhbGciOi")
    assert "eyJ" not in str(err.value) and "@" not in str(err.value)


def test_importing_main_creates_no_client(monkeypatch, restore_root_logger):
    monkeypatch.setenv("PLATFORM_ENV", "local")
    import importlib

    import platform_api.main as main

    importlib.reload(main)
    from fastapi.testclient import TestClient

    assert TestClient(main.app).get("/health").status_code == 200


# Beyond the brief's three: the rest of the adapters' logic, with fakes.

import importlib  # noqa: E402
from datetime import timedelta  # noqa: E402
from typing import Any  # noqa: E402

from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore  # noqa: E402
from platform_api.adapters.firestore_members import FirestoreMemberStore  # noqa: E402
from platform_api.adapters.firestore_ratelimit import FirestoreRateLimiter  # noqa: E402
from tests.fake_firestore import FakeFirestore  # noqa: E402
from tests.fixtures.people import T0  # noqa: E402


def test_the_key_sends_the_checksum_of_the_data_and_refuses_an_unverified_answer():
    import google_crc32c

    seen = {}

    class Recording(FakeKms):
        def mac_sign(self, request):
            seen.update(request)
            answer = super().mac_sign(request)
            answer.verified_data_crc32c = self.verified
            return answer

    key = Recording()
    key.verified = True
    KmsContactKey(key, NAME).mac(b"ana")
    assert seen == {"name": NAME, "data": b"ana", "data_crc32c": google_crc32c.value(b"ana")}
    key.verified = False
    with pytest.raises(RuntimeError, match="contact key"):
        KmsContactKey(key, NAME).mac(b"ana")


def test_a_key_name_that_is_not_a_key_version_is_refused():
    with pytest.raises(ValueError, match="PLATFORM_CONTACT_KEY"):
        KmsContactKey(FakeKms(), "projects/p/locations/l/keyRings/r/cryptoKeys/k")


class _Auth:
    """Stands for `firebase_admin.auth`: records calls, answers or raises as told."""

    def __init__(self, monkeypatch, **answers):
        import firebase_admin.auth as fa

        self.calls: list[tuple[str, tuple, dict]] = []
        for name in (
            "verify_id_token",
            "create_session_cookie",
            "verify_session_cookie",
            "revoke_refresh_tokens",
        ):
            monkeypatch.setattr(fa, name, self._recorder(name, answers.get(name)))

    def _recorder(self, name, answer):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if isinstance(answer, BaseException):
                raise answer
            return answer

        return call


def test_a_verified_token_gives_the_uid_and_the_address(monkeypatch):
    claims = {"uid": "u-ana", "email": "ana@example.org", "email_verified": True}
    auth = _Auth(monkeypatch, verify_id_token=claims)
    found = FirebaseIdentityProvider(app=None).verify_id_token("tok")
    assert (found.uid, found.email, found.email_verified) == ("u-ana", "ana@example.org", True)
    assert auth.calls == [("verify_id_token", ("tok",), {"app": None, "check_revoked": True})]


def test_a_token_without_an_address_is_refused(monkeypatch):
    _Auth(monkeypatch, verify_id_token={"uid": "u-ana"})
    with pytest.raises(InvalidToken):
        FirebaseIdentityProvider(app=None).verify_id_token("tok")


def test_sessions_are_created_checked_and_revoked_through_the_provider(monkeypatch):
    auth = _Auth(
        monkeypatch,
        create_session_cookie=b"cookie",
        verify_session_cookie={"uid": "u-ana"},
    )
    provider = FirebaseIdentityProvider(app=None)
    assert provider.create_session_cookie("tok", timedelta(days=14)) == "cookie"
    assert provider.verify_session_cookie("cookie") == "u-ana"
    provider.revoke_sessions("u-ana")
    assert auth.calls == [
        ("create_session_cookie", ("tok",), {"expires_in": timedelta(days=14), "app": None}),
        ("verify_session_cookie", ("cookie",), {"check_revoked": True, "app": None}),
        ("revoke_refresh_tokens", ("u-ana",), {"app": None}),
    ]


@pytest.mark.parametrize(
    "method", ["create_session_cookie", "verify_session_cookie", "revoke_refresh_tokens"]
)
def test_every_provider_error_becomes_invalid_token(monkeypatch, method):
    import firebase_admin.auth as fa

    errors = [
        fa.RevokedSessionCookieError("revoked eyJhb for ana@example.org"),
        ValueError("bad cookie eyJhb for ana@example.org"),
    ]
    provider = FirebaseIdentityProvider(app=None)
    call = {
        "create_session_cookie": lambda: provider.create_session_cookie("eyJhb", timedelta(days=1)),
        "verify_session_cookie": lambda: provider.verify_session_cookie("eyJhb"),
        "revoke_refresh_tokens": lambda: provider.revoke_sessions("u-ana"),
    }[method]
    for error in errors:
        _Auth(monkeypatch, **{method: error})
        with pytest.raises(InvalidToken) as err:
            call()
        assert "eyJ" not in str(err.value) and "@" not in str(err.value)
        assert err.value.__suppress_context__


def _reload_main(monkeypatch):
    from platform_api.entitlements import runtime as ent_runtime
    from platform_api.identity import runtime as id_runtime

    monkeypatch.setattr(ent_runtime, "_runtime", None)
    monkeypatch.setattr(id_runtime, "_runtime", None)
    import platform_api.main as main

    return importlib.reload(main)


def test_outside_local_a_missing_contact_key_stops_the_start(monkeypatch, restore_root_logger):
    monkeypatch.setenv("PLATFORM_ENV", "dev")
    monkeypatch.delenv("PLATFORM_CONTACT_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PLATFORM_CONTACT_KEY"):
        _reload_main(monkeypatch)


def test_outside_local_no_client_is_made_until_a_port_is_used(monkeypatch, restore_root_logger):
    import firebase_admin
    from google.cloud import firestore, kms

    made: list[str] = []

    def refuse(name):
        def build(*a, **k):
            made.append(name)
            raise RuntimeError("no client in this test")

        return build

    monkeypatch.setattr(firestore, "Client", refuse("firestore"))
    monkeypatch.setattr(kms, "KeyManagementServiceClient", refuse("kms"))
    monkeypatch.setattr(firebase_admin, "initialize_app", refuse("firebase"))
    monkeypatch.setenv("PLATFORM_ENV", "dev")
    monkeypatch.setenv("PLATFORM_CONTACT_KEY", NAME)
    main = _reload_main(monkeypatch)
    from fastapi.testclient import TestClient

    from platform_api.entitlements.runtime import get_runtime as ent_runtime
    from platform_api.identity.runtime import get_runtime as id_runtime

    assert TestClient(main.app).get("/health").status_code == 200
    assert made == []
    assert ent_runtime().key.version == "1" and made == []
    assert id_runtime().session_ttl == timedelta(days=14)
    assert id_runtime().request_refresh is None and id_runtime().last_reconcile_at is None
    with pytest.raises(RuntimeError, match="no client"):
        ent_runtime().store.get_contact("c1")
    assert made == ["firestore"]


def test_in_local_the_runtimes_are_in_memory(monkeypatch, restore_root_logger):
    monkeypatch.setenv("PLATFORM_ENV", "local")
    _reload_main(monkeypatch)
    from platform_api.entitlements.keys import LocalContactKey
    from platform_api.entitlements.runtime import get_runtime as ent_runtime
    from platform_api.entitlements.store import InMemoryStore
    from platform_api.identity.runtime import get_runtime as id_runtime
    from platform_api.identity.store import InMemoryMemberStore
    from platform_api.shared.ratelimit import InMemoryRateLimiter

    assert isinstance(ent_runtime().store, InMemoryStore)
    assert isinstance(ent_runtime().key, LocalContactKey)
    assert isinstance(id_runtime().members, InMemoryMemberStore)
    assert isinstance(id_runtime().limiter, InMemoryRateLimiter)


def test_a_job_runs_on_the_same_runtimes(monkeypatch, restore_root_logger):
    from platform_api import cli
    from platform_api.commerce import jobs as commerce_jobs
    from platform_api.entitlements import runtime as ent_runtime
    from platform_api.identity import runtime as id_runtime

    monkeypatch.setattr(ent_runtime, "_runtime", None)
    monkeypatch.setattr(id_runtime, "_runtime", None)
    monkeypatch.setenv("PLATFORM_ENV", "local")
    seen = []

    def job(settings):
        seen.append((ent_runtime.get_runtime(), id_runtime.get_runtime()))
        return 0

    monkeypatch.setattr(commerce_jobs, "JOBS", {"probe": job})
    assert cli.main(["job", "probe"]) == 0 and len(seen) == 1


def test_hooks_mode_starts_without_the_contact_key(monkeypatch, restore_root_logger):
    monkeypatch.setenv("PLATFORM_ENV", "dev")
    monkeypatch.setenv("PLATFORM_APP_MODE", "hooks")
    monkeypatch.delenv("PLATFORM_CONTACT_KEY", raising=False)
    main = _reload_main(monkeypatch)
    from fastapi.testclient import TestClient

    assert TestClient(main.app).get("/health").status_code == 200


def _no_key_job(monkeypatch, job):
    from platform_api import cli
    from platform_api.commerce import jobs as commerce_jobs
    from platform_api.entitlements import runtime as ent_runtime
    from platform_api.identity import runtime as id_runtime

    monkeypatch.setattr(ent_runtime, "_runtime", None)
    monkeypatch.setattr(id_runtime, "_runtime", None)
    monkeypatch.setenv("PLATFORM_ENV", "dev")
    monkeypatch.delenv("PLATFORM_CONTACT_KEY", raising=False)
    monkeypatch.setattr(commerce_jobs, "JOBS", {"probe": job})
    return cli.main(["job", "probe"])


def test_the_selfcheck_job_runs_without_the_contact_key(monkeypatch, restore_root_logger):
    import google.cloud.pubsub_v1 as pubsub

    sent = []

    class FakePublisher:
        def topic_path(self, project, topic):
            return f"projects/{project}/topics/{topic}"

        def publish(self, topic, data, **attrs):
            sent.append(attrs["ce-type"])
            return type("F", (), {"result": lambda self: "m-1"})()

    monkeypatch.setattr(pubsub, "PublisherClient", FakePublisher)
    from platform_api.jobs import JOBS

    assert _no_key_job(monkeypatch, JOBS["selfcheck"]) == 0
    assert sent == ["org.audhdneurobiology.platform.selfcheck.ran"]


def test_a_job_that_needs_the_contact_key_is_told_which_setting_is_missing(
    monkeypatch, restore_root_logger
):
    from platform_api.entitlements import public as ent_api

    def job(settings):
        ent_api.contact_id_for("ana@example.org")
        return 0

    with pytest.raises(RuntimeError, match="PLATFORM_CONTACT_KEY"):
        _no_key_job(monkeypatch, job)


# The Firestore stores on the fake client: the conformance checks and the shared tests.

from tests.entitlements.store_conformance import (  # noqa: E402
    check_a_claim_keeps_the_stored_status,
    check_a_stored_slug_keeps_its_counts,
    check_a_write_that_mixes_contacts_is_refused_whole,
    check_an_audit_only_write_appends_entries_and_nothing_else,
    check_create_if_absent_creates_once,
    check_merge_contact_sees_the_stored_contact_and_may_leave_it,
)


def test_the_firestore_store_passes_the_store_checks():
    for check in (
        check_a_write_that_mixes_contacts_is_refused_whole,
        check_create_if_absent_creates_once,
        check_merge_contact_sees_the_stored_contact_and_may_leave_it,
        check_a_stored_slug_keeps_its_counts,
        check_a_claim_keeps_the_stored_status,
    ):
        check(FirestoreEntitlementStore(FakeFirestore()))


def test_an_audit_only_write_on_firestore_never_opens_contacts():
    db = FakeFirestore()
    check_an_audit_only_write_appends_entries_and_nothing_else(FirestoreEntitlementStore(db))
    assert "contacts" not in db.reads + db.writes and set(db.writes) == {"audit_log"}


def test_a_query_for_many_contacts_is_split_into_parts_firestore_accepts():
    from tests.fixtures.people import record

    store = FirestoreEntitlementStore(FakeFirestore())
    ids = [f"c{i}" for i in range(65)]
    for cid in ids:
        store.write(cid, [record("ana", "stripe_year", contact_id=cid)], [])
    assert (
        len(store.entitlements_for_contacts(ids)) == 65
        and store.entitlements_for_contacts([]) == []
    )


def test_the_firestore_limiter_counts_like_the_in_memory_one():
    from platform_api.shared.ratelimit import InMemoryRateLimiter

    fake, memory = FirestoreRateLimiter(FakeFirestore()), InMemoryRateLimiter()
    day = timedelta(days=1)
    times = [T0 + timedelta(hours=h) for h in (0, 1, 2, 3, 23, 24, 25)]
    assert [fake.hit("support:u-ana", 3, day, t) for t in times] == [
        memory.hit("support:u-ana", 3, day, t) for t in times
    ]
    with pytest.raises(ValueError):
        fake.hit("a/b", 3, day, T0)


def test_firestore_members_round_trip_and_count():
    from platform_api.identity.models import SupportRequest

    store = FirestoreMemberStore(FakeFirestore())
    assert store.count() == 0 and store.get("u-ana") is None
    later = SupportRequest(
        id="r2", member_uid="u-ana", kind="other", note="n", status="open", created_at=T0
    )
    earlier = later.model_copy(update={"id": "r1", "created_at": T0 - timedelta(days=1)})
    store.add_support_request(later)
    store.add_support_request(earlier)
    assert [r.id for r in store.support_requests()] == ["r1", "r2"]


@pytest.fixture
def ent(monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.entitlements import runtime as runtime_module
    from platform_api.entitlements.keys import LocalContactKey
    from platform_api.entitlements.runtime import Runtime
    from platform_api.shared.bus import InMemoryBus

    runtime = Runtime(
        FirestoreEntitlementStore(FakeFirestore()), LocalContactKey(b"test"), InMemoryBus()
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


@pytest.fixture
def idn(ent: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.identity import runtime as runtime_module
    from platform_api.identity.provider import FakeIdentityProvider
    from platform_api.identity.runtime import Runtime
    from tests.fixtures.people import EMAIL

    db = FakeFirestore()
    runtime = Runtime(
        members=FirestoreMemberStore(db),
        provider=FakeIdentityProvider(EMAIL),
        bus=ent.bus,
        session_ttl=timedelta(days=14),
        limiter=FirestoreRateLimiter(db),
        request_refresh=None,
        last_reconcile_at=None,
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


@pytest.fixture
def world(idn: Any, ent: Any) -> Any:
    from fastapi.testclient import TestClient

    from platform_api.app import create_app
    from platform_api.settings import Settings
    from tests.entitlements.test_campaigns import campaign
    from tests.entitlements.test_reconcile import run, state
    from tests.fixtures.launch import TERMS

    ent.store.put_launch_config(TERMS)
    ent.store.put_campaigns(
        [campaign(), campaign("members", audience="public", grant=None, is_default=True)]
    )
    run(
        ent,
        [
            state("ana", "sub_a"),
            state("hal", "sub_h", grant="status:substack_paid", interval="month"),
        ],
    )
    return TestClient(create_app(Settings()))


# The same assertions as the in-memory tests, collected here on the Firestore stores.
from tests.entitlements.test_campaigns import (  # noqa: E402
    test_applying_twice_creates_one_grant_and_only_for_a_member,  # noqa: F401
)
from tests.entitlements.test_claim_grant import (  # noqa: E402
    test_first_sign_in_claims_what_was_waiting,  # noqa: F401
)
from tests.entitlements.test_contacts import (  # noqa: E402
    test_upsert_keeps_the_first_address_and_merges_channels,  # noqa: F401
)
from tests.entitlements.test_reconcile import (  # noqa: E402
    test_first_run_creates_and_second_run_changes_nothing,  # noqa: F401
)
from tests.identity.test_http_member import (  # noqa: E402
    test_the_sixth_request_in_a_day_is_limited,  # noqa: F401
)
from tests.identity.test_sessions import (  # noqa: E402
    test_ana_is_recognised_claims_her_record_and_gets_the_grant,  # noqa: F401
)


def test_the_firestore_member_store_passes_the_store_checks():
    from tests.identity.store_conformance import (
        check_merge_member_sees_the_stored_member_and_may_leave_it,
    )

    check_merge_member_sees_the_stored_member_and_may_leave_it(
        FirestoreMemberStore(FakeFirestore())
    )


# Lifetimes (plan Task 9, contracts section 4): Firestore deletes a document after expires_at.


def _expiries(db: FakeFirestore, collection: str) -> list[Any]:
    return [data.get("expires_at") for (name, _), data in db.docs.items() if name == collection]


def test_every_audit_entry_expires_two_years_after_it_was_written():
    from tests.entitlements.store_conformance import _audit
    from tests.fixtures.people import record

    db = FakeFirestore()
    store = FirestoreEntitlementStore(db)
    entry = _audit("x").model_copy(update={"at": T0})
    store.write("c-ana", [record("ana", "stripe_year")], [entry])
    store.write("", [], [entry])
    store.create_if_absent(record("bo", "owner_grant", contact_id="c-ana"), entry)
    store.write("c-cy", [record("cy", "stripe_year", contact_id="c-cy")], [])
    assert len(store.claim_records("c-cy", "u-cy", T0 + timedelta(days=1))) == 1
    assert _expiries(db, "audit_log") == [T0 + timedelta(days=730)] * 3 + [T0 + timedelta(days=731)]
    assert len(store.audit_for("x")) == 3  # the extra field is ignored on the way back


def test_a_support_request_expires_a_year_after_it_was_made():
    from platform_api.identity.models import SupportRequest

    db = FakeFirestore()
    store = FirestoreMemberStore(db)
    store.add_support_request(
        SupportRequest(
            id="r1", member_uid="u-ana", kind="other", note="n", status="open", created_at=T0
        )
    )
    assert _expiries(db, "support_requests") == [T0 + timedelta(days=365)]
    assert [r.id for r in store.support_requests()] == ["r1"]


def test_a_rate_limit_expires_two_days_after_its_window_ends():
    db = FakeFirestore()
    limiter = FirestoreRateLimiter(db)
    limiter.hit("support:u-ana", 3, timedelta(days=1), T0 + timedelta(hours=1))
    # Windows are aligned to the epoch: this one runs from T0 to T0 + 1 day.
    assert _expiries(db, "rate_limits") == [T0 + timedelta(days=3)]
