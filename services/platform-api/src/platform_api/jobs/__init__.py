"""Shared jobs. Importing this module creates no cloud client."""

from collections.abc import Callable

from platform_api.settings import Settings


def _selfcheck(settings: Settings) -> int:
    from google.cloud.pubsub_v1 import PublisherClient  # type: ignore[import-untyped]

    from platform_api.jobs.selfcheck import run_selfcheck
    from platform_api.shared.bus import PubSubBus

    bus = PubSubBus(PublisherClient(), settings.gcp_project, settings.events_topic)
    run_selfcheck(bus)
    return 0


JOBS: dict[str, Callable[[Settings], int]] = {"selfcheck": _selfcheck}
