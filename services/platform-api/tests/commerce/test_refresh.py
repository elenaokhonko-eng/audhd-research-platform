# tests/commerce/test_refresh.py
from datetime import timedelta

import pytest

from platform_api.commerce import public as commerce
from platform_api.commerce.ports import InMemoryStripeReader
from platform_api.commerce.refresh import RateLimited
from tests.commerce.test_mapping import sub
from tests.fixtures.people import T0


def test_a_stale_check_starts_the_job_once(com):
    first = commerce.request_refresh("u-bo", T0)
    second = commerce.request_refresh("u-ed", T0 + timedelta(seconds=1))
    assert (first.check, second.check, com.jobs.started) == (
        "started",
        "already_running",
        [com.settings.reconcile_job],
    )
    assert first.next_allowed_at == T0 + timedelta(seconds=60)


def test_a_run_completed_in_the_last_minute_is_reused(com):
    com.stripe = InMemoryStripeReader([sub("ana")])
    commerce.stripe_reconcile(False, "schedule", T0)
    ticket = commerce.request_refresh("u-bo", T0 + timedelta(seconds=30))
    assert (ticket.check, ticket.last_completed_at, com.jobs.started) == ("fresh", T0, [])
    assert commerce.request_refresh("u-ed", T0 + timedelta(seconds=90)).check == "started"


def test_one_member_is_limited_to_one_a_minute_and_six_an_hour(com):
    commerce.request_refresh("u-bo", T0)
    with pytest.raises(RateLimited) as err:
        commerce.request_refresh("u-bo", T0 + timedelta(seconds=20))
    assert 0 < err.value.retry_after <= 60
    for i in range(1, 6):
        commerce.request_refresh("u-bo", T0 + timedelta(minutes=2 * i))
    with pytest.raises(RateLimited):
        commerce.request_refresh("u-bo", T0 + timedelta(minutes=13))


def test_sign_in_is_not_limited_but_shares_the_start_slot(com):
    assert commerce.request_refresh(None, T0).check == "started"
    assert commerce.request_refresh(None, T0 + timedelta(seconds=5)).check == "already_running"


def test_without_a_job_starter_nothing_starts(com):
    com.jobs = None
    assert commerce.request_refresh("u-bo", T0).check == "fresh"


def test_the_route_answers_202_and_maps_the_limit(com, member_client):
    client, cookie = member_client("bo")
    first = client.post("/v1/me/refresh-access", headers=cookie)
    assert first.status_code == 202 and first.json()["check"] == "started"
    again = client.post("/v1/me/refresh-access", headers=cookie)
    assert again.status_code == 429 and again.json()["error"]["retry_after"] > 0


# Beyond the brief: the controller's decisions for Task 3.


def test_a_blocked_run_in_the_last_minute_is_reused_but_not_reported_as_checked(com):
    run_id = com.runs.start("stripe_reconcile", False, "schedule", T0)
    com.runs.finish(run_id, "completed", "blocked", {}, T0)
    ticket = commerce.request_refresh("u-bo", T0 + timedelta(seconds=30))
    assert (ticket.check, ticket.last_completed_at, com.jobs.started) == ("fresh", None, [])


def test_without_a_job_name_nothing_starts(com):
    com.settings = com.settings.model_copy(update={"reconcile_job": ""})
    assert commerce.request_refresh("u-bo", T0).check == "fresh"
    assert com.jobs.started == []


def test_a_job_that_cannot_be_started_answers_503(com, member_client):
    from platform_api.commerce.ports import JobStartError

    class Refusing:
        def start(self, job):
            raise JobStartError("the job could not be started")

    com.jobs = Refusing()
    client, cookie = member_client("bo")
    r = client.post("/v1/me/refresh-access", headers=cookie)
    assert r.status_code == 503 and r.json()["error"]["code"] == "unavailable"


def test_a_running_reconcile_is_not_started_again(com):
    com.runs.start("stripe_reconcile", False, "schedule", T0)
    ticket = commerce.request_refresh("u-bo", T0 + timedelta(minutes=2))
    assert (ticket.check, com.jobs.started) == ("already_running", [])


def test_a_run_left_running_for_over_ten_minutes_no_longer_blocks(com):
    com.runs.start("stripe_reconcile", False, "schedule", T0)
    assert commerce.request_refresh("u-bo", T0 + timedelta(minutes=11)).check == "started"


def test_the_running_bound_outlasts_the_job_timeout():
    from platform_api.commerce.refresh import RUNNING_BOUND

    # Infra's stripe-reconcile job times out after 540 seconds; a run still `running` past
    # that was stopped without finishing.
    assert timedelta(seconds=540) < RUNNING_BOUND <= timedelta(minutes=10)


def test_the_route_refuses_a_caller_without_a_session(com, member_client):
    client, _ = member_client("bo")
    r = client.post("/v1/me/refresh-access")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_the_route_refuses_a_member_before_the_terms(com, member_client):
    from tests.identity.test_sessions import sign_in

    client, _ = member_client("bo")
    cookie = {"X-Member-Session": sign_in(client, "ed").json()["session"]["cookie"]}
    r = client.post("/v1/me/refresh-access", headers=cookie)
    assert r.status_code == 409 and r.json()["error"]["code"] == "terms_required"
    assert com.jobs.started == []


def test_the_start_slot_is_taken_once_across_threads():
    import threading
    import time

    from platform_api.commerce.ports import InMemoryRunStore

    class SlowReads(dict):
        def get(self, *args):
            held = super().get(*args)
            time.sleep(0.01)  # widens the gap between the read and the write
            return held

    runs, results = InMemoryRunStore(), []
    runs._last_start = SlowReads()
    barrier = threading.Barrier(8)

    def take():
        barrier.wait()
        results.append(runs.acquire_start_slot("stripe_reconcile", T0, timedelta(seconds=60)))

    threads = [threading.Thread(target=take) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False] * 7 + [True]


def test_after_a_blocked_guard_check_again_waits_a_quarter_of_an_hour(com):
    run_id = com.runs.start("stripe_reconcile", False, "schedule", T0)
    com.runs.finish(run_id, "completed", "blocked", {}, T0)
    early = commerce.request_refresh("u-bo", T0 + timedelta(minutes=5))
    assert (early.check, early.last_completed_at, com.jobs.started) == ("fresh", None, [])
    late = commerce.request_refresh("u-bo", T0 + timedelta(minutes=16))
    assert (late.check, com.jobs.started) == ("started", [com.settings.reconcile_job])
