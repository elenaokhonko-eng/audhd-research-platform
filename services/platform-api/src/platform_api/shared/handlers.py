"""Registry of event handlers, keyed by event type."""

from collections.abc import Callable

from platform_api.shared.events import EVENT_PREFIX, DomainEvent

Handler = Callable[[DomainEvent], None]


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def register(self, type_suffix: str, handler: Handler) -> None:
        """Register for the event type EVENT_PREFIX + type_suffix."""
        self._handlers.setdefault(EVENT_PREFIX + type_suffix, []).append(handler)

    def handlers_for(self, event_type: str) -> list[Handler]:
        return list(self._handlers.get(event_type, []))
