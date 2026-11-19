from datetime import UTC, datetime

from platform_api.shared.inbox import InMemoryInbox

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def test_inbox_remembers_and_tolerates_repeats() -> None:
    inbox = InMemoryInbox()
    assert inbox.seen("e1") is False
    inbox.record("e1", event_type="t", received_at=NOW)
    inbox.record("e1", event_type="t", received_at=NOW)
    assert inbox.seen("e1") is True
    assert inbox.seen("e2") is False
