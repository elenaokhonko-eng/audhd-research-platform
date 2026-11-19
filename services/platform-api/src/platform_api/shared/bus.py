"""Event bus port. Publishing is a call on a client the caller passes in."""

from typing import Protocol

from google.cloud.pubsub_v1 import PublisherClient  # type: ignore[import-untyped]

from platform_api.shared.events import DomainEvent, assert_no_personal_data


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> str:
        """Publish the event and return the message id."""
        ...


class InMemoryBus:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> str:
        assert_no_personal_data(event)
        self.published.append(event)
        return f"mem-{len(self.published)}"


class PubSubBus:
    def __init__(self, publisher: PublisherClient, project: str, topic: str) -> None:
        self._publisher = publisher
        self._topic_path = publisher.topic_path(project, topic)

    def publish(self, event: DomainEvent) -> str:
        assert_no_personal_data(event)
        future = self._publisher.publish(
            self._topic_path,
            event.model_dump_json().encode("utf-8"),
            **{"ce-id": event.id, "ce-type": event.type, "ce-subject": event.subject},
        )
        return str(future.result())
