from datetime import UTC, datetime

import pytest

from platform_api.entitlements.models import AuditEntry, Entitlement, entitlement_id
from platform_api.entitlements.store import EntitlementStore, InMemoryStore

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


def check_a_write_that_mixes_contacts_is_refused_whole(store: EntitlementStore) -> None:
    mine, other = _ent("c1"), _ent("c2")
    audit = AuditEntry(
        at=NOW,
        actor="policy:x",
        action="entitlement.created",
        subject="c1",
        reason=None,
        evidence={},
    )
    with pytest.raises(ValueError):
        store.write("c1", [mine, other], [audit])
    assert store.get_entitlement(mine.entitlement_id) is None
    assert store.get_entitlement(other.entitlement_id) is None
    assert store.audit_for("c1") == []


def test_in_memory_store_refuses_a_write_that_mixes_contacts():
    check_a_write_that_mixes_contacts_is_refused_whole(InMemoryStore())


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


def test_in_memory_store_takes_an_audit_only_write_and_refuses_records_without_a_contact():
    check_an_audit_only_write_appends_entries_and_nothing_else(InMemoryStore())
