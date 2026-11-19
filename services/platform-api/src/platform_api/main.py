from datetime import datetime
from functools import cache

from platform_api.app import Deps, create_app
from platform_api.settings import Settings
from platform_api.shared.auth import push_identity_from_token
from platform_api.shared.bus import EventBus
from platform_api.shared.events import DomainEvent
from platform_api.shared.handlers import HandlerRegistry
from platform_api.shared.inbox import Inbox
from platform_api.shared.logging import configure_logging

_settings = Settings()
configure_logging(_settings.service_name)


@cache
def _bus() -> EventBus:
    from google.cloud.pubsub_v1 import PublisherClient  # type: ignore[import-untyped]

    from platform_api.shared.bus import PubSubBus

    return PubSubBus(PublisherClient(), _settings.gcp_project, _settings.events_topic)


@cache
def _inbox() -> Inbox:
    from google.cloud import firestore

    from platform_api.shared.inbox import FirestoreInbox

    return FirestoreInbox(firestore.Client(project=_settings.gcp_project))


class _LazyBus:
    """Builds the real client on first publish, so importing needs no credentials."""

    def publish(self, event: DomainEvent) -> str:
        return _bus().publish(event)


class _LazyInbox:
    def seen(self, event_id: str) -> bool:
        return _inbox().seen(event_id)

    def record(self, event_id: str, *, event_type: str, received_at: datetime) -> None:
        _inbox().record(event_id, event_type=event_type, received_at=received_at)


app = create_app(
    _settings,
    Deps(
        bus=_LazyBus(),
        inbox=_LazyInbox(),
        registry=HandlerRegistry(),
        verify_push=lambda t: push_identity_from_token(
            t, allowed_email=_settings.push_service_account
        ),
    ),
)
