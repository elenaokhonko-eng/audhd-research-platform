"""Checks every MemberStore must pass: in memory, on the fake Firestore and on the emulator.

Not a test module: each `check_…(store)` is called from a test that names its store.
"""

from datetime import UTC, datetime, timedelta

import pytest

from platform_api.identity.models import Member, SupportRequest
from platform_api.identity.store import MemberStore

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def _member(uid: str) -> Member:
    return Member(
        uid=uid,
        primary_contact_id="c1",
        linked_contact_ids=[],
        email="ana@example.org",
        display_name=None,
        terms_accepted=None,
        joined_via=None,
        status="active",
        created_at=NOW,
        last_seen_at=NOW,
    )


def check_merge_member_sees_the_stored_member_and_may_leave_it(store: MemberStore) -> None:
    assert store.merge_member("u-ana", lambda held: None) is None
    assert store.get("u-ana") is None
    created = store.merge_member("u-ana", lambda held: held or _member("u-ana"))
    assert created == store.get("u-ana") == _member("u-ana")

    later = NOW + timedelta(days=1)

    def seen(held: Member | None) -> Member | None:
        assert held is not None
        return held.model_copy(update={"last_seen_at": later})

    def deleted(held: Member | None) -> Member | None:
        assert held is not None
        return held.model_copy(
            update={"status": "deletion_requested", "deletion_requested_at": later}
        )

    store.merge_member("u-ana", deleted)
    merged = store.merge_member("u-ana", seen)
    assert merged is not None and merged == store.get("u-ana")
    assert (merged.status, merged.deletion_requested_at, merged.last_seen_at) == (
        "deletion_requested",
        later,
        later,
    )
    assert store.merge_member("u-ana", lambda held: None) == merged
    with pytest.raises(ValueError):
        store.merge_member("u-ana", lambda held: _member("u-bo"))
    assert store.get("u-bo") is None and store.get("u-ana") == merged


def _request(rid: str, uid: str) -> SupportRequest:
    return SupportRequest(
        id=rid, member_uid=uid, kind="other", note="n", status="open", created_at=NOW
    )


def check_delete_removes_one_member_and_their_requests(store: MemberStore) -> None:
    store.put(_member("u-ana"))
    store.put(_member("u-bo"))
    for rid, uid in (("r1", "u-ana"), ("r2", "u-bo"), ("r3", "u-ana")):
        store.add_support_request(_request(rid, uid))

    assert store.delete_support_requests("u-ana") == 2
    assert [r.id for r in store.support_requests()] == ["r2"]
    assert store.delete_support_requests("u-ana") == 0
    assert store.delete("u-ana") is True
    assert store.get("u-ana") is None and store.count() == 1
    assert store.delete("u-ana") is False
    assert store.get("u-bo") == _member("u-bo")


def check_members_with_status_finds_only_that_status(store: MemberStore) -> None:
    asked = _member("u-ana").model_copy(
        update={"status": "deletion_requested", "deletion_requested_at": NOW}
    )
    store.put(asked)
    store.put(_member("u-bo"))
    assert store.members_with_status("deletion_requested") == [asked]
    assert [m.uid for m in store.members_with_status("active")] == ["u-bo"]
