"""The Firestore stores against the emulator: the same assertions as the in-memory tests.

Runs in CI with FIRESTORE_EMULATOR_HOST set; skipped without it. Each test has its own
project id, so tests never see each other's documents.
"""

import os
import threading
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif("FIRESTORE_EMULATOR_HOST" not in os.environ, reason="emulator not running"),
]


def _client() -> Any:
    from google.cloud import firestore

    return firestore.Client(project=f"test-{uuid4().hex[:12]}")


@pytest.fixture(params=["in_memory", "firestore"])
def stores(request: pytest.FixtureRequest) -> Any:
    """A factory of the three stores: in memory, or on the emulator."""
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from platform_api.adapters.firestore_members import FirestoreMemberStore
    from platform_api.adapters.firestore_ratelimit import FirestoreRateLimiter
    from platform_api.entitlements.store import InMemoryStore
    from platform_api.identity.store import InMemoryMemberStore
    from platform_api.shared.ratelimit import InMemoryRateLimiter

    if request.param == "in_memory":
        return InMemoryStore(), InMemoryMemberStore(), InMemoryRateLimiter()
    client = _client()
    return (
        FirestoreEntitlementStore(client),
        FirestoreMemberStore(client),
        FirestoreRateLimiter(client),
    )


@pytest.fixture
def ent(stores: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.entitlements import runtime as runtime_module
    from platform_api.entitlements.keys import LocalContactKey
    from platform_api.entitlements.runtime import Runtime
    from platform_api.shared.bus import InMemoryBus

    runtime = Runtime(stores[0], LocalContactKey(b"test"), InMemoryBus())
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


@pytest.fixture
def idn(stores: Any, ent: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.identity import runtime as runtime_module
    from platform_api.identity.provider import FakeIdentityProvider
    from platform_api.identity.runtime import Runtime
    from tests.fixtures.people import EMAIL

    runtime = Runtime(
        members=stores[1],
        provider=FakeIdentityProvider(EMAIL),
        bus=ent.bus,
        session_ttl=timedelta(days=14),
        limiter=stores[2],
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


# The five in-memory tests, collected here with the fixtures above (both stores).
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


def test_the_firestore_store_passes_the_store_checks() -> None:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from tests.entitlements.store_conformance import (
        check_a_claim_keeps_the_stored_status,
        check_a_stored_slug_keeps_its_counts,
        check_a_write_that_mixes_contacts_is_refused_whole,
        check_an_audit_only_write_appends_entries_and_nothing_else,
        check_create_if_absent_creates_once,
        check_merge_contact_sees_the_stored_contact_and_may_leave_it,
    )

    for check in (
        check_a_write_that_mixes_contacts_is_refused_whole,
        check_an_audit_only_write_appends_entries_and_nothing_else,
        check_create_if_absent_creates_once,
        check_merge_contact_sees_the_stored_contact_and_may_leave_it,
        check_a_stored_slug_keeps_its_counts,
        check_a_claim_keeps_the_stored_status,
    ):
        check(FirestoreEntitlementStore(_client()))


def _at_once(*calls: Any) -> list[Any]:
    """Run the calls on threads that start together; their results in order."""
    barrier = threading.Barrier(len(calls))
    results: list[Any] = [None] * len(calls)
    errors: list[BaseException] = []

    def run(i: int) -> None:
        try:
            barrier.wait()
            results[i] = calls[i]()
        except BaseException as exc:  # reported below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(calls))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    return results


def test_two_writers_create_one_grant() -> None:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from platform_api.entitlements.models import AuditEntry
    from tests.fixtures.people import T0, record

    client = _client()
    first, second = FirestoreEntitlementStore(client), FirestoreEntitlementStore(client)
    grant = record("ana", "launch_grant")
    audit = AuditEntry(
        at=T0,
        actor="policy:founding",
        action="entitlement.granted",
        subject=grant.entitlement_id,
        reason="launch_grant",
        evidence={"campaign": "founding"},
    )
    results = _at_once(
        lambda: first.create_if_absent(grant, audit), lambda: second.create_if_absent(grant, audit)
    )
    assert sorted(results) == [False, True]
    assert len(list(client.collection("entitlements").stream())) == 1
    assert len(first.audit_for(grant.entitlement_id)) == 1


def _firestore_runtime(monkeypatch: pytest.MonkeyPatch) -> Any:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from platform_api.entitlements import runtime as runtime_module
    from platform_api.entitlements.keys import LocalContactKey
    from platform_api.entitlements.runtime import Runtime
    from platform_api.shared.bus import InMemoryBus

    runtime = Runtime(FirestoreEntitlementStore(_client()), LocalContactKey(b"test"), InMemoryBus())
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    return runtime


def test_two_upserts_on_different_channels_both_survive(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.entitlements import public as ent_api
    from platform_api.entitlements.models import ChannelsPatch
    from tests.fixtures.people import EMAIL

    runtime = _firestore_runtime(monkeypatch)
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch())
    _at_once(
        lambda: ent_api.upsert_contact(
            EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"})
        ),
        lambda: ent_api.upsert_contact(
            EMAIL["ana"], ChannelsPatch(stripe={"has_substack_subscription": True})
        ),
    )
    channels = runtime.store.get_contact(cid).channels
    assert channels["platform"]["member_uid"] == "u-ana"
    assert channels["stripe"] == {"has_substack_subscription": True}


def test_two_members_claiming_one_contact_leave_one_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.entitlements import public as ent_api
    from platform_api.entitlements.models import ChannelsPatch
    from tests.fixtures.people import EMAIL, record

    runtime = _firestore_runtime(monkeypatch)
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch())
    runtime.store.write(cid, [record("ana", "stripe_year", contact_id=cid)], [])
    claimed = _at_once(
        lambda: ent_api.claim_for_member("u-one", cid),
        lambda: ent_api.claim_for_member("u-two", cid),
    )
    owner = runtime.store.get_contact(cid).channels["platform"]["member_uid"]
    assert owner in ("u-one", "u-two")
    assert [len(c) for c in claimed] == ([1, 0] if owner == "u-one" else [0, 1])
    loser = "u-two" if owner == "u-one" else "u-one"
    assert runtime.store.entitlements_for_member(loser) == []
    assert runtime.store.contact_ids_for_member(owner) == [cid]


def test_two_first_sign_ins_create_one_member() -> None:
    from platform_api.adapters.firestore_members import FirestoreMemberStore
    from platform_api.identity.models import Member
    from tests.fixtures.people import T0

    store = FirestoreMemberStore(_client())
    member = Member(
        uid="u-ana",
        primary_contact_id="c1",
        linked_contact_ids=[],
        email="ana@example.org",
        display_name=None,
        terms_accepted=None,
        joined_via="founding",
        status="active",
        created_at=T0,
        last_seen_at=T0,
    )
    results = _at_once(
        lambda: store.create_if_absent(member),
        lambda: store.create_if_absent(member.model_copy(update={"joined_via": "members"})),
    )
    assert sorted(results) == [False, True] and store.count() == 1


def test_a_claim_and_an_end_at_once_leave_the_record_ended() -> None:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from tests.fixtures.people import T0, record

    client = _client()
    claimer, runner = FirestoreEntitlementStore(client), FirestoreEntitlementStore(client)
    live = record("bo", "stripe_year", contact_id="c-bo")
    runner.write("c-bo", [live], [])
    ended = live.model_copy(update={"status": "expired", "updated_by": "run:r2"})
    _at_once(
        lambda: claimer.claim_records("c-bo", "u-bo", T0),
        lambda: runner.write("c-bo", [ended], []),
    )
    # Whichever lands first, the end is kept. (A run's whole-document write may blank a claim
    # that landed just before it; no access is lost, since unclaimed records still count.)
    held = runner.get_entitlement(live.entitlement_id)
    assert held is not None and held.status == "expired"


def _expiries(client: Any, collection: str) -> list[Any]:
    return [s.to_dict().get("expires_at") for s in client.collection(collection).stream()]


def test_an_audit_entry_on_firestore_expires_two_years_after_it() -> None:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from platform_api.entitlements.models import AuditEntry
    from tests.fixtures.people import T0

    client = _client()
    entry = AuditEntry(
        at=T0, actor="owner:acc-1", action="admin.read", subject="admin", reason=None, evidence={}
    )
    FirestoreEntitlementStore(client).write("", [], [entry])
    assert _expiries(client, "audit_log") == [T0 + timedelta(days=730)]


def test_a_support_request_on_firestore_expires_a_year_after_it() -> None:
    from platform_api.adapters.firestore_members import FirestoreMemberStore
    from platform_api.identity.models import SupportRequest
    from tests.fixtures.people import T0

    client = _client()
    FirestoreMemberStore(client).add_support_request(
        SupportRequest(
            id="r1", member_uid="u-ana", kind="other", note="n", status="open", created_at=T0
        )
    )
    assert _expiries(client, "support_requests") == [T0 + timedelta(days=365)]


def test_a_rate_limit_on_firestore_expires_two_days_after_its_window() -> None:
    from platform_api.adapters.firestore_ratelimit import FirestoreRateLimiter
    from tests.fixtures.people import T0

    client = _client()
    FirestoreRateLimiter(client).hit("support:u-ana", 3, timedelta(days=1), T0)
    assert _expiries(client, "rate_limits") == [T0 + timedelta(days=3)]


def test_the_firestore_member_store_passes_the_store_checks() -> None:
    from platform_api.adapters.firestore_members import FirestoreMemberStore
    from tests.identity.store_conformance import (
        check_merge_member_sees_the_stored_member_and_may_leave_it,
    )

    check_merge_member_sees_the_stored_member_and_may_leave_it(FirestoreMemberStore(_client()))


def test_the_firestore_stores_pass_the_deletion_checks() -> None:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from platform_api.adapters.firestore_members import FirestoreMemberStore
    from tests.entitlements.store_conformance import (
        check_forget_contact_removes_the_contact_and_its_records_only,
    )
    from tests.identity.store_conformance import (
        check_delete_removes_one_member_and_their_requests,
        check_members_with_status_finds_only_that_status,
    )

    check_forget_contact_removes_the_contact_and_its_records_only(
        FirestoreEntitlementStore(_client())
    )
    check_delete_removes_one_member_and_their_requests(FirestoreMemberStore(_client()))
    check_members_with_status_finds_only_that_status(FirestoreMemberStore(_client()))


def test_a_forgotten_contact_on_firestore_leaves_one_entry_that_expires() -> None:
    from platform_api.adapters.firestore_entitlements import FirestoreEntitlementStore
    from platform_api.entitlements.models import AuditEntry, Contact
    from tests.fixtures.people import T0, record

    client = _client()
    store = FirestoreEntitlementStore(client)
    store.put_contact(
        Contact(
            contact_id="c-ana",
            key_version="local",
            email="ana@example.org",
            channels={},
            invite={"campaign": None, "state": "none"},
            created_at=T0,
            updated_at=T0,
        )
    )
    store.write("c-ana", [record("ana", "stripe_year")], [])

    def entry(removed: int) -> AuditEntry:
        return AuditEntry(
            at=T0,
            actor="owner:acc-1",
            action="contact.forgotten",
            subject="c-ana",
            reason=None,
            evidence={"entitlements_removed": str(removed)},
        )

    assert store.forget_contact("c-ana", entry) == 1
    assert list(client.collection("contacts").stream()) == []
    assert list(client.collection("entitlements").stream()) == []
    assert _expiries(client, "audit_log") == [T0 + timedelta(days=730)]


# The deletion journey on both stores.
from tests.identity.test_deletion import (  # noqa: E402
    test_a_contact_another_member_owns_survives_the_delete,  # noqa: F401
    test_a_deleted_member_leaves_nothing_but_one_audit_entry,  # noqa: F401
    test_a_second_delete_is_harmless,  # noqa: F401
    test_only_requests_are_pending_and_oldest_first,  # noqa: F401
    test_records_that_name_the_member_hold_no_address_and_are_left_to_expire,  # noqa: F401
    test_the_same_address_signs_in_again_as_a_new_free_member,  # noqa: F401
)
