from platform_api.identity.store import InMemoryMemberStore
from tests.identity.store_conformance import (
    check_merge_member_sees_the_stored_member_and_may_leave_it,
)


def test_in_memory_member_store_merges_a_member_in_one_step():
    check_merge_member_sees_the_stored_member_and_may_leave_it(InMemoryMemberStore())
