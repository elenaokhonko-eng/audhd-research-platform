from datetime import UTC, datetime

from platform_api.shared import clock


def test_add_months_keeps_the_day_or_takes_the_last_day():
    assert clock.add_months(datetime(2026, 1, 31, tzinfo=UTC), 1) == datetime(
        2026, 2, 28, tzinfo=UTC
    )
    assert clock.add_months(datetime(2026, 11, 20, tzinfo=UTC), 3) == datetime(
        2027, 2, 20, tzinfo=UTC
    )
    assert clock.add_months(datetime(2026, 11, 20, tzinfo=UTC), 12) == datetime(
        2027, 11, 20, tzinfo=UTC
    )


def test_utcnow_is_aware_and_the_fixture_replaces_it():
    from tests.fixtures.people import T0

    assert clock.utcnow() == T0
