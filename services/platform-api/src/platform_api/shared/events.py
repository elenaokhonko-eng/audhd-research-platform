"""CloudEvents envelope. Events carry ids only; email addresses are refused."""

import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, PlainSerializer

EVENT_PREFIX = "org.audhdneurobiology."
EVENT_SOURCE = "//audhdneurobiology.org/platform-api"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class PersonalDataInEvent(ValueError):
    """Raised when an event would carry an email address."""


def _utc_z(value: datetime) -> str:
    # Naive datetimes are treated as UTC; aware ones are converted.
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


UtcTime = Annotated[datetime, PlainSerializer(_utc_z, return_type=str)]


class DomainEvent(BaseModel):
    specversion: Literal["1.0"]
    id: str
    type: str
    source: str
    subject: str
    time: UtcTime
    datacontenttype: Literal["application/json"]
    data: dict[str, Any]


def _contains_email(value: object) -> bool:
    if isinstance(value, str):
        return _EMAIL.search(value) is not None
    if isinstance(value, dict):
        return any(_contains_email(k) or _contains_email(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_email(v) for v in value)
    return False


def assert_no_personal_data(event: DomainEvent) -> None:
    """Raise PersonalDataInEvent if any field of the serialised event looks like an email."""
    if _contains_email(event.model_dump(mode="json")):
        raise PersonalDataInEvent("events carry ids only, not email addresses")


def new_event(
    type_suffix: str,
    subject: str,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
    now: datetime | None = None,
) -> DomainEvent:
    if not type_suffix or type_suffix.startswith(EVENT_PREFIX):
        raise ValueError("type_suffix must be non-empty and must not repeat the prefix")
    if event_id is None:
        event_id = uuid.uuid4().hex
    elif not event_id:
        raise ValueError("event_id must not be empty")
    event = DomainEvent(
        specversion="1.0",
        id=event_id,
        type=EVENT_PREFIX + type_suffix,
        source=EVENT_SOURCE,
        subject=subject,
        time=now or datetime.now(UTC),
        datacontenttype="application/json",
        data=data,
    )
    assert_no_personal_data(event)
    return event
