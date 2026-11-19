"""Receiver for Pub/Sub push deliveries of platform events."""

import base64
import binascii
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from platform_api.shared.auth import NotAuthorised, PushIdentity
from platform_api.shared.events import DomainEvent
from platform_api.shared.handlers import HandlerRegistry
from platform_api.shared.inbox import Inbox

log = logging.getLogger(__name__)


def _bearer(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _decode_event(body: Any) -> DomainEvent | None:
    """Return the event, or None if the body can never become one."""
    try:
        data = body["message"]["data"]
        raw = base64.b64decode(data, validate=True)
        return DomainEvent.model_validate_json(raw)
    except (KeyError, TypeError, ValueError, binascii.Error, ValidationError):
        return None


def _process(inbox: Inbox, registry: HandlerRegistry, event: DomainEvent) -> int:
    if inbox.seen(event.id):
        return 204
    try:
        for handler in registry.handlers_for(event.type):
            handler(event)
    except Exception:
        log.exception("Handler failed for event %s of type %s", event.id, event.type)
        return 500
    inbox.record(event.id, event_type=event.type, received_at=datetime.now(UTC))
    return 204


def build_push_router(
    *,
    inbox: Inbox,
    registry: HandlerRegistry,
    verify: Callable[[str], PushIdentity],
) -> APIRouter:
    router = APIRouter()

    @router.post("/internal/pubsub/platform-events")
    async def receive(request: Request) -> Response:
        token = _bearer(request)
        if token is None:
            return Response(status_code=401)
        try:
            verify(token)
        except NotAuthorised as exc:
            return Response(status_code=403 if exc.reason == "wrong_identity" else 401)

        try:
            body = await request.json()
        except ValueError:
            body = None
        event = _decode_event(body)
        if event is None:
            # Never log the message: it could hold personal data. It can never
            # succeed, so acknowledge it rather than have it redelivered.
            log.error("Dropped a push message that is not a valid platform event")
            return Response(status_code=204)

        # Firestore and handlers block; keep them off the event loop.
        status = await run_in_threadpool(_process, inbox, registry, event)
        return Response(status_code=status)

    return router
