import os
from datetime import UTC, datetime

import pytest
from google.cloud import firestore

from platform_api.shared.inbox import FirestoreInbox

pytestmark = pytest.mark.integration


@pytest.mark.skipif("FIRESTORE_EMULATOR_HOST" not in os.environ, reason="emulator not running")
def test_firestore_inbox_round_trip() -> None:
    inbox = FirestoreInbox(firestore.Client(project="test"), collection="inbox_test")
    now = datetime(2026, 11, 16, tzinfo=UTC)
    assert inbox.seen("e-int-1") is False
    inbox.record("e-int-1", event_type="t", received_at=now)
    inbox.record("e-int-1", event_type="t", received_at=now)
    assert inbox.seen("e-int-1") is True
