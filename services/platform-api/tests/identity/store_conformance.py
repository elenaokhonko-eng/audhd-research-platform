"""Checks every MemberStore must pass: in memory, on the fake Firestore and on the emulator.

Not a test module: each `check_…(store)` is called from a test that names its store.
"""

from datetime import UTC, datetime, timedelta

import pytest

from platform_api.identity.models import Member
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
