import json
from datetime import UTC, datetime
from typing import Any

import pytest

from platform_api.shared.bus import InMemoryBus, PubSubBus
from platform_api.shared.events import DomainEvent, PersonalDataInEvent, new_event


class FakeFuture:
    def result(self, timeout: float | None = None) -> str:
        return "m-1"


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []

    def topic_path(self, project: str, topic: str) -> str:
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic: str, data: bytes, **attrs: str) -> FakeFuture:
        self.calls.append((topic, data, attrs))
        return FakeFuture()


def test_in_memory_bus_keeps_events() -> None:
    bus = InMemoryBus()
    e = new_event("x.y.happened", "s", {"n": 1})
    bus.publish(e)
    assert bus.published == [e]


def test_pubsub_bus_publishes_json_with_ce_attributes() -> None:
    pub: Any = FakePublisher()
    e = new_event("x.y.happened", "s-1", {"n": 1}, event_id="e1")
    assert PubSubBus(pub, "proj", "platform.events").publish(e) == "m-1"
    topic, data, attrs = pub.calls[0]
    assert topic == "projects/proj/topics/platform.events"
    assert json.loads(data)["id"] == "e1"
    assert attrs == {
        "ce-id": "e1",
        "ce-type": "org.audhdneurobiology.x.y.happened",
        "ce-subject": "s-1",
    }


def _event_with_email() -> DomainEvent:
    return DomainEvent(
        specversion="1.0",
        id="e1",
        type="org.audhdneurobiology.x.y.happened",
        source="s",
        subject="c_1",
        time=datetime(2026, 11, 16, tzinfo=UTC),
        datacontenttype="application/json",
        data={"who": "ana@example.org"},
    )


def test_in_memory_bus_refuses_a_directly_built_event_with_an_email() -> None:
    bus = InMemoryBus()
    with pytest.raises(PersonalDataInEvent):
        bus.publish(_event_with_email())
    assert bus.published == []


def test_pubsub_bus_refuses_a_directly_built_event_with_an_email() -> None:
    pub: Any = FakePublisher()
    with pytest.raises(PersonalDataInEvent):
        PubSubBus(pub, "proj", "t").publish(_event_with_email())
    assert pub.calls == []
