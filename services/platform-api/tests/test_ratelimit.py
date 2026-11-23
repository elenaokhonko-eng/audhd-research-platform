from datetime import UTC, datetime, timedelta

from platform_api.shared.ratelimit import InMemoryRateLimiter

NOW = datetime(2026, 11, 20, 0, 0, 10, tzinfo=UTC)


def test_a_fixed_window_allows_the_limit_then_says_how_long_to_wait() -> None:
    limiter = InMemoryRateLimiter()
    minute = timedelta(minutes=1)
    assert [limiter.hit("k", 2, minute, NOW) for _ in range(2)] == [None, None]
    assert limiter.hit("k", 2, minute, NOW) == 50
    assert limiter.hit("other", 2, minute, NOW) is None
    assert limiter.hit("k", 2, minute, NOW + timedelta(seconds=50)) is None
