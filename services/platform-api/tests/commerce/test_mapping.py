from datetime import timedelta

import pytest

from platform_api.commerce.mapping import classify, to_state
from platform_api.commerce.models import StripeSubscription
from platform_api.commerce.settings import CommerceSettings
from tests.fixtures.people import EMAIL, T0

S = CommerceSettings(
    stripe_substack_application="ca_test_substack", substack_grant_year="tier:paid"
)


def sub(name="ana", **over):
    base = dict(
        id=f"sub_test_{name}",
        status="active",
        application="ca_test_substack",
        metadata={},
        customer_email=EMAIL[name],
        interval="year",
        start_date=T0 - timedelta(days=200),
        current_period_end=T0 + timedelta(days=165),
        past_due_since=None,
        provider_time=T0,
    )
    return StripeSubscription(**{**base, **over})


def test_an_annual_substack_subscription_becomes_a_paid_tier_state():
    state = to_state(sub(), S, T0)
    assert (state.source, state.source_ref, state.grant, state.status, state.plan_interval) == (
        "substack_stripe",
        "sub_test_ana",
        "tier:paid",
        "active",
        "year",
    )
    assert (state.started_at, state.valid_until) == (
        T0 - timedelta(days=200),
        T0 + timedelta(days=165),
    )


def test_a_monthly_plan_is_recorded_as_the_setting_says():
    assert to_state(sub("hal", interval="month"), S, T0).grant == "status:substack_paid"
    both = CommerceSettings(
        stripe_substack_application="ca_test_substack", substack_grant_month="tier:paid"
    )
    assert to_state(sub("hal", interval="month"), both, T0).grant == "tier:paid"
    weekly = to_state(sub("hal", interval="week"), S, T0)
    assert (weekly.plan_interval, weekly.grant) == (None, "status:substack_paid")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("trialing", "active"),
        ("active", "active"),
        ("paused", "expired"),
        ("canceled", "expired"),
        ("unpaid", "expired"),
        ("incomplete_expired", "expired"),
    ],
)
def test_statuses(status, expected):
    assert to_state(sub(status=status), S, T0).status == expected


def test_past_due_is_grace_for_twenty_one_days_then_expired():
    in_grace = to_state(sub(status="past_due", past_due_since=T0 - timedelta(days=20)), S, T0)
    assert (in_grace.status, in_grace.valid_until) == ("grace", T0 + timedelta(days=1))
    assert (
        to_state(sub(status="past_due", past_due_since=T0 - timedelta(days=21)), S, T0).status
        == "expired"
    )
    assert to_state(sub(status="past_due", past_due_since=None), S, T0) == "past_due_unknown"


def test_what_is_not_a_usable_substack_subscription_gives_no_state():
    assert to_state(sub(status="incomplete"), S, T0) == "incomplete"
    assert to_state(sub(customer_email=None), S, T0) == "no_address"
    assert to_state(sub(customer_email="not an address"), S, T0) == "bad_address"
    assert (
        to_state(sub(application="ca_other"), S, T0) == "not_substack"
        and classify(sub(application=None), S) is None
    )
    assert classify(sub(), CommerceSettings(stripe_substack_application="")) is None


def test_the_sandbox_marker_works_only_when_switched_on_and_never_in_prod():
    marked = sub(application=None, metadata={"test_channel": "substack"})
    assert classify(marked, S) is None
    assert classify(marked, CommerceSettings(stripe_test_channel_metadata=True)) == "substack"
    with pytest.raises(ValueError):
        CommerceSettings(env="prod", stripe_test_channel_metadata=True)


def test_a_subscription_never_prints_its_address():
    assert "@" not in repr(sub()) and "@" not in repr(to_state(sub(), S, T0))


def test_a_subscription_never_prints_an_address_held_in_its_metadata():
    assert "@" not in repr(sub(metadata={"note": EMAIL["ana"]}))


def test_grace_days_must_be_at_least_one():
    with pytest.raises(ValueError):
        CommerceSettings(grace_days=0)


def test_an_unknown_interval_is_always_a_status_whatever_the_settings_say():
    both = CommerceSettings(
        stripe_substack_application="ca_test_substack",
        substack_grant_month="tier:paid",
        substack_grant_year="tier:paid",
    )
    weekly = to_state(sub("hal", interval="week"), both, T0)
    none = to_state(sub("hal", interval=None), both, T0)
    assert (weekly.plan_interval, weekly.grant) == (None, "status:substack_paid")
    assert none.grant == "status:substack_paid"
