"""Registry of event handlers, keyed by event type."""

from collections.abc import Callable

from platform_api.shared.events import EVENT_PREFIX, DomainEvent

Handler = Callable[[DomainEvent], None]


class HandlerRegistry:
    """Handlers by event type.

    Handlers must be safe to run twice. The inbox is a shortcut, not a guarantee:
    if one handler fails, Pub/Sub redelivers the event and every handler runs
    again, and two concurrent deliveries can both pass `seen`. See
    docs/architecture/09-events-and-data-model.md section 4.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def register(self, type_suffix: str, handler: Handler) -> None:
        """Register for the event type EVENT_PREFIX + type_suffix.

        The handler must be safe to run twice for the same event (see the class note).
        """
        self._handlers.setdefault(EVENT_PREFIX + type_suffix, []).append(handler)

    def handlers_for(self, event_type: str) -> list[Handler]:
        return list(self._handlers.get(event_type, []))
