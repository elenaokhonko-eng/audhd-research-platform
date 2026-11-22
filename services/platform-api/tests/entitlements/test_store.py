from platform_api.entitlements.store import InMemoryStore
from tests.entitlements.store_conformance import (
    check_a_stored_slug_keeps_its_counts,
    check_a_write_that_mixes_contacts_is_refused_whole,
    check_an_audit_only_write_appends_entries_and_nothing_else,
    check_create_if_absent_creates_once,
    check_merge_contact_sees_the_stored_contact_and_may_leave_it,
)


def test_in_memory_store_refuses_a_write_that_mixes_contacts():
    check_a_write_that_mixes_contacts_is_refused_whole(InMemoryStore())


def test_in_memory_store_takes_an_audit_only_write_and_refuses_records_without_a_contact():
    check_an_audit_only_write_appends_entries_and_nothing_else(InMemoryStore())


def test_in_memory_store_creates_a_record_once():
    check_create_if_absent_creates_once(InMemoryStore())


def test_in_memory_store_merges_a_contact_in_one_step():
    check_merge_contact_sees_the_stored_contact_and_may_leave_it(InMemoryStore())


def test_in_memory_store_keeps_the_counts_of_a_stored_campaign():
    check_a_stored_slug_keeps_its_counts(InMemoryStore())


def test_in_memory_store_claims_waiting_records_and_keeps_their_status():
    from tests.entitlements.store_conformance import check_a_claim_keeps_the_stored_status

    check_a_claim_keeps_the_stored_status(InMemoryStore())
