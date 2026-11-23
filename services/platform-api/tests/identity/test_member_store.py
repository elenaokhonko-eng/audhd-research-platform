from platform_api.identity.store import InMemoryMemberStore
from tests.identity.store_conformance import (
    check_delete_removes_one_member_and_their_requests,
    check_members_with_status_finds_only_that_status,
    check_merge_member_sees_the_stored_member_and_may_leave_it,
)


def test_in_memory_member_store_merges_a_member_in_one_step():
    check_merge_member_sees_the_stored_member_and_may_leave_it(InMemoryMemberStore())


def test_in_memory_member_store_deletes_one_member_and_their_requests():
    check_delete_removes_one_member_and_their_requests(InMemoryMemberStore())


def test_in_memory_member_store_finds_members_by_status():
    check_members_with_status_finds_only_that_status(InMemoryMemberStore())
