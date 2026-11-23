# tests/commerce/test_promotions.py
from datetime import timedelta

import pytest

from platform_api.commerce import public as commerce
from platform_api.commerce.models import Promotion
from platform_api.commerce.ports import InMemoryStripeReader
from platform_api.entitlements.models import LaunchConfig
from tests.commerce.test_mapping import sub
from tests.fixtures.people import T0

START, END = T0 + timedelta(days=6), T0 + timedelta(days=11)


def promo(**over):
    base = dict(
        id="offer-1",
        channel="substack_offer",
        audience=["free_members", "guests"],
        plan_interval="year",
        starts_at=START,
        ends_at=END,
        substack_offer_url="https://example.org/offer",
        display={"badge": "b", "headline": "h", "body": "x"},
        counts={},
    )
    return Promotion(**{**base, **over})


@pytest.fixture
def open_shop(com, ent):
    ent.store.put_launch_config(
        LaunchConfig(
            join_open=True,
            promotions_open=True,
            substack_account_url="https://example.org/subscribe",
        )
    )
    commerce.put_promotions([promo()], "owner:acc-1")
    return com


@pytest.mark.parametrize(
    ("when", "shown"),
    [(START - timedelta(seconds=1), 0), (START, 1), (END - timedelta(seconds=1), 1), (END, 0)],
)
def test_a_promotion_shows_only_inside_its_window(open_shop, when, shown):
    assert len(commerce.active_promotions("guests", when)) == shown


def test_the_switch_hides_everything_and_the_audience_filters(open_shop, ent):
    assert commerce.active_promotions("paid_members", START) == []
    ent.store.put_launch_config(LaunchConfig(join_open=True, promotions_open=False))
    assert commerce.active_promotions("guests", START) == []


def test_the_view_carries_no_counts_and_the_offer_link(open_shop):
    [view] = commerce.active_promotions("guests", START)
    assert view.url == "https://example.org/offer" and "counts" not in view.model_dump()


def test_upgrade_options_by_kind_of_member(open_shop, signed_in):
    free = commerce.upgrade_options(signed_in("bo"), START)
    assert [(r.kind, r.available, r.url) for r in free.routes] == [
        ("substack", True, "https://example.org/offer"),
        ("platform_only", False, None),
    ]
    assert free.promotion.id == "offer-1"
    assert (
        commerce.upgrade_options(signed_in("bo"), END).routes[0].url
        == "https://example.org/subscribe"
    )
    monthly = commerce.upgrade_options(signed_in("hal"), START)
    assert [(r.kind, r.url) for r in monthly.routes] == [
        ("substack_change_plan", "https://example.org/subscribe")
    ] and monthly.promotion is None
    paid = commerce.upgrade_options(signed_in("ana"), START)
    assert (paid.routes, paid.promotion) == ([], None)


def test_cy_is_counted_once_and_a_reader_who_already_paid_is_not(open_shop, ent):
    open_shop.stripe = InMemoryStripeReader([sub("ana")])
    commerce.stripe_reconcile(False, "schedule", T0)
    inside = START + timedelta(days=1)
    open_shop.stripe = InMemoryStripeReader(
        [
            sub("ana"),
            sub("cy", start_date=inside),
            sub("ana", id="sub_test_ana_2", start_date=inside),
        ]
    )
    commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=1))
    commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=2))
    [stored] = open_shop.promotions.list()
    counted = [
        e for e in ent.bus.published if e.type.endswith("commerce.promotion.upgrade_counted")
    ]
    assert (
        stored.counts == {"upgrades_in_window": 1}
        and len(counted) == 1
        and "@" not in counted[0].model_dump_json()
    )


def test_the_owner_route_validates(open_shop, owner_client):
    good = promo(id="offer-2").model_dump(mode="json")
    assert owner_client.put("/v1/admin/promotions", json={"promotions": [good]}).json() == {
        "written": 1
    }
    for bad in (
        {**good, "ends_at": good["starts_at"]},
        {**good, "substack_offer_url": "http://example.org/x"},
    ):
        assert (
            owner_client.put("/v1/admin/promotions", json={"promotions": [bad]}).status_code == 422
        )
    assert (
        owner_client.put("/v1/admin/promotions", json={"promotions": [good, good]}).status_code
        == 422
    )


def test_the_public_route_is_cacheable_for_a_minute(open_shop, owner_client):
    r = owner_client.get("/v1/public/promotions/active", headers={"Authorization": ""})
    assert (
        r.status_code == 200
        and r.headers["cache-control"] == "public, max-age=60"
        and "promotions" in r.json()
    )
