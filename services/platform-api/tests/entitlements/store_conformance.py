"""Checks every EntitlementStore must pass: the in-memory store and the Firestore store.

Not a test module: each `check_…(store)` is called from a test that names its store.
"""

from datetime import UTC, datetime

import pytest

from platform_api.entitlements.models import (
    AuditEntry,
    Campaign,
    Contact,
    Entitlement,
    entitlement_id,
)
from platform_api.entitlements.store import EntitlementStore

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def _ent(contact_id: str) -> Entitlement:
    return Entitlement(
        entitlement_id=entitlement_id("grant", "campaign:x", contact_id, "tier:paid"),
        contact_id=contact_id,
        member_uid=None,
        grant="tier:paid",
        source="grant",
        source_ref="campaign:x",
        access_scope=None,
        plan_interval=None,
        valid_from=None,
        valid_until=None,
        status="active",
        updated_at=NOW,
        updated_by="policy:x",
    )


def _audit(subject: str) -> AuditEntry:
    return AuditEntry(
        at=NOW,
        actor="policy:x",
        action="entitlement.created",
        subject=subject,
        reason=None,
        evidence={},
    )


def _contact(contact_id: str, **channels: dict[str, object]) -> Contact:
    return Contact(
        contact_id=contact_id,
        key_version="local",
        email="ana@example.org",
        channels=dict(channels),
        invite={"campaign": None, "state": "none"},
        created_at=NOW,
        updated_at=NOW,
    )


def check_a_write_that_mixes_contacts_is_refused_whole(store: EntitlementStore) -> None:
    mine, other = _ent("c1"), _ent("c2")
    with pytest.raises(ValueError):
        store.write("c1", [mine, other], [_audit("c1")])
    assert store.get_entitlement(mine.entitlement_id) is None
    assert store.get_entitlement(other.entitlement_id) is None
    assert store.audit_for("c1") == []


def check_an_audit_only_write_appends_entries_and_nothing_else(store: EntitlementStore) -> None:
    entry = AuditEntry(
        at=NOW,
        actor="owner:acc-1",
        action="launch.switched",
        subject="config/launch",
        reason=None,
        evidence={"changed": "join_open"},
    )
    store.write("", [], [entry])
    assert store.audit_for("config/launch") == [entry]
    stray = _ent("")
    with pytest.raises(ValueError):
        store.write("", [stray], [])
    assert store.get_entitlement(stray.entitlement_id) is None


def check_create_if_absent_creates_once(store: EntitlementStore) -> None:
    record = _ent("c1")
    assert store.create_if_absent(record, _audit(record.entitlement_id)) is True
    assert store.create_if_absent(record, _audit(record.entitlement_id)) is False
    assert store.get_entitlement(record.entitlement_id) == record
    assert len(store.audit_for(record.entitlement_id)) == 1


def check_merge_contact_sees_the_stored_contact_and_may_leave_it(store: EntitlementStore) -> None:
    assert store.merge_contact("c1", lambda held: None) is None
    assert store.get_contact("c1") is None
    created = store.merge_contact("c1", lambda held: held or _contact("c1", stripe={"a": 1}))
    assert created == store.get_contact("c1") == _contact("c1", stripe={"a": 1})

    def add_platform(held: Contact | None) -> Contact | None:
        assert held is not None
        return held.model_copy(update={"channels": {**held.channels, "platform": {"b": 2}}})

    merged = store.merge_contact("c1", add_platform)
    assert merged is not None and merged.channels == {"stripe": {"a": 1}, "platform": {"b": 2}}
    assert store.merge_contact("c1", lambda held: None) == merged
    with pytest.raises(ValueError):
        store.merge_contact("c1", lambda held: _contact("c2"))
    assert store.get_contact("c2") is None


def check_a_stored_slug_keeps_its_counts(store: EntitlementStore) -> None:
    def campaign(headline: str, counts: dict[str, int]) -> Campaign:
        return Campaign(
            slug="founding",
            audience="substack_paid",
            opens_at=None,
            closes_at=None,
            is_default=True,
            grant=None,
            copy={"headline": headline, "body": "b", "cta": "c"},
            counts=counts,
        )

    store.put_campaigns([campaign("one", {"arrivals": 2})])
    store.add_to_campaign_count("founding", "arrivals")
    store.add_to_campaign_count("founding", "grants_created", 3)
    store.put_campaigns([campaign("two", {})])
    stored = store.get_campaign("founding")
    assert stored is not None and stored.copy_["headline"] == "two"
    assert stored.counts == {"arrivals": 3, "grants_created": 3}
    with pytest.raises(LookupError):
        store.add_to_campaign_count("nope", "arrivals")
