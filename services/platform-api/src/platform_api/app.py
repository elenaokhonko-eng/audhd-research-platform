from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import FastAPI

from platform_api.settings import Settings

if TYPE_CHECKING:
    from platform_api.shared.auth import PushIdentity
    from platform_api.shared.bus import EventBus
    from platform_api.shared.handlers import HandlerRegistry
    from platform_api.shared.inbox import Inbox


@dataclass
class Deps:
    bus: EventBus | None = None
    inbox: Inbox | None = None
    registry: HandlerRegistry | None = None
    verify_push: Callable[[str], PushIdentity] | None = None


def create_app(settings: Settings, deps: Deps | None = None) -> FastAPI:
    local = settings.env == "local"
    app = FastAPI(
        title=settings.service_name,
        docs_url="/docs" if local else None,
        redoc_url="/redoc" if local else None,
        openapi_url="/openapi.json" if local else None,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "mode": settings.app_mode,
            "env": settings.env,
        }

    if settings.app_mode == "api":

        @app.get("/v1/ping")
        def ping() -> dict[str, bool]:
            return {"pong": True}

        # Mounted only here, and only when every dependency is supplied.
        if (
            deps is not None
            and deps.inbox is not None
            and deps.registry is not None
            and deps.verify_push is not None
        ):
            from platform_api.shared.pubsub_push import build_push_router

            app.include_router(
                build_push_router(inbox=deps.inbox, registry=deps.registry, verify=deps.verify_push)
            )

    return app
