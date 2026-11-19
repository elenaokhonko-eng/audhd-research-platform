from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from platform_api.shared.events import EVENT_SOURCE, PersonalDataInEvent, new_event


class _Holder(BaseModel):
    note: str


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def test_new_event_builds_a_cloudevent() -> None:
    e = new_event(
        "membership.tier.changed", "c_0123", {"from": "paid", "to": "free"}, event_id="e1", now=NOW
    )
    assert e.model_dump(mode="json") == {
        "specversion": "1.0",
        "id": "e1",
        "type": "org.audhdneurobiology.membership.tier.changed",
        "source": EVENT_SOURCE,
        "subject": "c_0123",
        "time": "2026-11-16T12:00:00Z",
        "datacontenttype": "application/json",
        "data": {"from": "paid", "to": "free"},
    }


def test_event_id_defaults_to_a_fresh_uuid() -> None:
    a = new_event("x.y.happened", "s", {})
    b = new_event("x.y.happened", "s", {})
    assert a.id != b.id and len(a.id) == 32


@pytest.mark.parametrize(
    "subject,data",
    [
        ("someone@example.org", {}),
        ("c_1", {"email": "someone@example.org"}),
        ("c_1", {"items": [{"note": "write to Some.One+tag@Mail.Example.org please"}]}),
        ("c_1", {"holder": _Holder(note="ana@example.org")}),
        ("c_1", {"set": frozenset({"ana@example.org"})}),
    ],
)
def test_email_anywhere_in_the_event_is_rejected(subject: str, data: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(PersonalDataInEvent):
        new_event("x.y.happened", subject, data)


def test_event_id_that_looks_like_an_email_is_rejected() -> None:
    with pytest.raises(PersonalDataInEvent):
        new_event("x.y.happened", "s", {}, event_id="ana@example.org")


def test_an_empty_event_id_is_refused() -> None:
    with pytest.raises(ValueError):
        new_event("x.y.happened", "s", {}, event_id="")


def test_type_suffix_must_not_repeat_the_prefix_or_be_empty() -> None:
    with pytest.raises(ValueError):
        new_event("org.audhdneurobiology.x.y.happened", "s", {})
    with pytest.raises(ValueError):
        new_event("", "s", {})
