from platform_api.shared.bus import EventBus
from platform_api.shared.events import new_event


def run_selfcheck(bus: EventBus) -> str:
    """Publish one event through the bus, print its id and return it."""
    event = new_event("platform.selfcheck.ran", "platform-api", {"check": "bus"})
    bus.publish(event)
    print(event.id)
    return event.id
