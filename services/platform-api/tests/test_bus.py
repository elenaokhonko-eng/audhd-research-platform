import json
from typing import Any

from platform_api.shared.bus import InMemoryBus, PubSubBus
from platform_api.shared.events import new_event


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
