from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from substack_desk.models import DirectoryListing, SubscriberRecord
from substack_desk.ports import SubscriberDirectory

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def record(**over):
    base = {"email": "ana@example.org", "type": "paid", "plan_interval": "year", "paid_until": NOW, "since": NOW}
    return SubscriberRecord(**{**base, **over})


def test_email_is_trimmed_and_lower_cased():
    assert record(email="  Ana@Example.ORG ").email == "ana@example.org"


@pytest.mark.parametrize(
    "bad",
    [
        "ana",
        "@example.org",
        "ana@",
        "a@b@c",
        "",
        "ana smith@example.org",
        "ana@ example.org",
        "ana@example.org\x00",
        "ana@exa\tmple.org",
    ],
)
def test_a_value_that_is_not_an_email_is_refused(bad):
    with pytest.raises(ValidationError):
        record(email=bad)


def test_a_since_without_a_zone_is_refused():
    with pytest.raises(ValidationError):
        record(since=datetime(2026, 11, 20))


def test_an_exported_at_without_a_zone_is_refused():
    with pytest.raises(ValidationError):
        DirectoryListing(records=[], complete=True, rejected_rows=0, exported_at=datetime(2026, 11, 20))


def test_a_time_without_a_zone_is_refused():
    with pytest.raises(ValidationError):
        record(paid_until=datetime(2026, 11, 20))


@pytest.mark.parametrize("kind", ["paid", "comp", "gift", "group_seat", "founding", "lifetime"])
def test_every_type_except_free_is_paid(kind):
    assert record(type=kind).is_paid is True


def test_free_is_not_paid():
    assert record(type="free", plan_interval=None, paid_until=None).is_paid is False


def test_an_unknown_type_is_refused():
    with pytest.raises(ValidationError):
        record(type="vip")


def test_a_record_cannot_be_changed_after_it_is_built():
    with pytest.raises(ValidationError):
        record().email = "other@example.org"


def test_a_listing_holds_paying_readers_only():
    with pytest.raises(ValidationError):
        DirectoryListing(records=[record(type="free", plan_interval=None, paid_until=None)],
                         complete=True, rejected_rows=0, exported_at=NOW)


def test_rejected_rows_cannot_be_negative():
    with pytest.raises(ValidationError):
        DirectoryListing(records=[], complete=True, rejected_rows=-1, exported_at=NOW)


def test_anything_with_list_paid_is_a_directory():
    class Fixed:
        def list_paid(self) -> DirectoryListing:
            return DirectoryListing(records=[record()], complete=True, rejected_rows=0, exported_at=NOW)

    directory: SubscriberDirectory = Fixed()
    assert directory.list_paid().records[0].email == "ana@example.org"
