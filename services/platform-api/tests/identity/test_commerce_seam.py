"""Sign-in asks Commerce for a fresh look at Stripe through the seam `configure_runtimes` sets."""

import logging
from datetime import timedelta
from typing import Any

import pytest

from tests.fixtures.people import T0
from tests.identity.test_sessions import sign_in

JOB = "projects/p/locations/l/jobs/stripe-reconcile"


@pytest.fixture
def wired(world: Any, idn: Any, ent: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Commerce on in-memory ports with a job to start, and identity's seam set as at start-up."""
    from platform_api.adapters import sign_in_last_reconcile, sign_in_refresh
    from platform_api.commerce import runtime as runtime_module
    from platform_api.commerce.ports import InMemoryJobStarter, InMemoryRunStore
    from platform_api.commerce.runtime import Runtime
    from platform_api.commerce.settings import CommerceSettings

    runtime = Runtime(
        settings=CommerceSettings(reconcile_job=JOB),
        stripe=None,
        runs=InMemoryRunStore(),
        bus=ent.bus,
        jobs=InMemoryJobStarter(),
    )
    monkeypatch.setattr(runtime_module, "_runtime", runtime)
    idn.request_refresh = sign_in_refresh
    idn.last_reconcile_at = sign_in_last_reconcile
    return runtime


def _at(monkeypatch: pytest.MonkeyPatch, when: Any) -> None:
    from platform_api.shared import clock

    monkeypatch.setattr(clock, "utcnow", lambda: when)


def test_a_sign_in_with_no_completed_reconcile_starts_the_job_once(wired, world):
    body = sign_in(world, "bo").json()
    assert body["join"]["check"] == "started" and wired.jobs.started == [JOB]


def test_a_second_sign_in_within_a_minute_does_not_raise(wired, world, monkeypatch):
    assert sign_in(world, "bo").json()["join"]["check"] == "started"
    _at(monkeypatch, T0 + timedelta(seconds=30))
    again = sign_in(world, "ed")
    assert again.status_code == 200 and again.json()["join"]["check"] == "started"
    assert wired.jobs.started == [JOB]  # the start slot is held for the minute


def test_a_job_that_cannot_start_leaves_sign_in_working(wired, world):
    from platform_api.commerce.ports import JobStartError

    class Broken:
        def start(self, job: str) -> None:
            raise JobStartError("the job could not be started")

    wired.jobs = Broken()
    response = sign_in(world, "bo")
    assert response.status_code == 200 and response.json()["join"]["check"] == "fresh"


def test_a_rate_limited_refresh_is_fresh_and_the_uid_is_not_passed_on(monkeypatch):
    from platform_api import adapters
    from platform_api.commerce import public as commerce

    asked = []

    def limited(uid, now):
        asked.append(uid)
        raise commerce.RateLimited(retry_after=30)

    monkeypatch.setattr(commerce, "request_refresh", limited)
    assert adapters.sign_in_refresh("u-bo", T0) == "fresh" and asked == [None]


def test_a_recent_reconcile_makes_the_sign_in_fresh_without_a_start(wired, world):
    run_id = wired.runs.start("stripe_reconcile", False, "schedule", T0 - timedelta(minutes=5))
    wired.runs.finish(run_id, "completed", "passed", {}, T0 - timedelta(minutes=4))
    assert sign_in(world, "bo").json()["join"]["check"] == "fresh" and wired.jobs.started == []


def test_a_run_store_that_fails_never_fails_a_sign_in(wired, world, monkeypatch, caplog):
    def latest(*args, **kwargs):
        # stands in for FailedPrecondition: the library's text names the project
        raise RuntimeError("the query requires an index in projects/p")

    monkeypatch.setattr(wired.runs, "latest", latest)
    with caplog.at_level(logging.ERROR):
        response = sign_in(world, "bo")
    assert response.status_code == 200 and response.json()["join"]["check"] == "fresh"
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert "last_reconcile_read_failed error=RuntimeError" in messages
    assert "sign_in_refresh_failed error=RuntimeError" in messages
    assert "projects/p" not in caplog.text and wired.jobs.started == []


def test_any_other_error_of_the_refresh_is_fresh(monkeypatch, caplog):
    from platform_api import adapters
    from platform_api.commerce import public as commerce

    def broken(uid, now):
        raise ValueError("ana@example.org")

    monkeypatch.setattr(commerce, "request_refresh", broken)
    with caplog.at_level(logging.ERROR):
        assert adapters.sign_in_refresh("u-bo", T0) == "fresh"
    assert [r.getMessage() for r in caplog.records] == ["sign_in_refresh_failed error=ValueError"]
    assert "@" not in caplog.text


def test_a_last_reconcile_that_cannot_be_read_is_none(monkeypatch, caplog):
    from platform_api import adapters
    from platform_api.commerce import public as commerce

    def broken():
        raise RuntimeError("projects/p")

    monkeypatch.setattr(commerce, "last_reconcile_completed_at", broken)
    with caplog.at_level(logging.ERROR):
        assert adapters.sign_in_last_reconcile() is None
    assert [r.getMessage() for r in caplog.records] == [
        "last_reconcile_read_failed error=RuntimeError"
    ]
