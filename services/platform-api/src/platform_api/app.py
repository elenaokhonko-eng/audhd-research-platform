from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from platform_api.modules import FEATURE_MODULES
from platform_api.settings import Settings
from platform_api.shared.http import install_error_handlers

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


def _route_paths(router: Any, prefix: str = "") -> Iterator[str]:
    """Every path a router serves, following routers included inside it."""
    for route in router.routes:
        original = getattr(route, "original_router", None)
        if original is not None:
            inner = prefix + route.include_context.prefix
            yield from _route_paths(original, inner)
        else:
            yield prefix + getattr(route, "path", "")


def _require_hooks_paths(router: Any) -> None:
    for path in _route_paths(router):
        if not path.startswith("/hooks/"):
            raise RuntimeError(
                f"hooks mode may serve only /health and /hooks/*, but a route is at {path!r}"
            )


def create_app(settings: Settings, deps: Deps | None = None) -> FastAPI:
    local = settings.env == "local"
    app = FastAPI(
        title=settings.service_name,
        docs_url="/docs" if local else None,
        redoc_url="/redoc" if local else None,
        openapi_url="/openapi.json" if local else None,
    )

    app.state.settings = settings
    install_error_handlers(app)

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

    # Looked up at call time, so a module's routers can be replaced in a test.
    attr = "router" if settings.app_mode == "api" else "hooks_router"
    for name in FEATURE_MODULES:
        http = importlib.import_module(f"platform_api.{name}.http")
        router = getattr(http, attr)
        if settings.app_mode == "hooks":
            _require_hooks_paths(router)
        app.include_router(router)

    return app
