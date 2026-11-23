# tests/commerce/test_promotions.py
import logging
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


def test_a_failure_while_counting_leaves_the_reconcile_completed(
    open_shop, ent, caplog, monkeypatch
):
    def broken(promotion_id, contact_id):
        raise RuntimeError("the store is down")

    monkeypatch.setattr(open_shop.promotions, "count_once", broken)
    inside = START + timedelta(days=1)
    open_shop.stripe = InMemoryStripeReader([sub("cy", start_date=inside)])
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=1))
    assert (run.state, run.guard, run.counts["created"], run.counts["upgrade_count_failed"]) == (
        "completed",
        "passed",
        1,
        1,
    )
    assert [e.source_ref for e in ent.store.entitlements_by_source("substack_stripe")] == [
        "sub_test_cy"
    ]
    assert "reconcile_failed" not in caplog.text and "alert=" not in caplog.text
    assert "upgrade_count_failed" in caplog.text and "the store is down" not in caplog.text
    assert any(e.type.endswith("commerce.reconcile.completed") for e in ent.bus.published)


def test_a_subscription_that_moves_to_another_address_is_not_counted_again(open_shop):
    from tests.fixtures.people import EMAIL

    inside = START + timedelta(days=1)
    open_shop.stripe = InMemoryStripeReader([sub("cy", start_date=inside)])
    commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=1))
    open_shop.stripe = InMemoryStripeReader(
        [sub("cy", start_date=inside, customer_email=EMAIL["di"])]
    )
    run = commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=2))
    assert run.counts["moved"] == 1
    [stored] = open_shop.promotions.list()
    assert stored.counts == {"upgrades_in_window": 1}


def test_every_owner_call_on_promotions_is_audited_once_with_its_outcome(
    open_shop, owner_client, ent
):
    good = promo(id="offer-2").model_dump(mode="json")
    assert owner_client.put("/v1/admin/promotions", json={"promotions": [good]}).status_code == 200
    assert (
        owner_client.put("/v1/admin/promotions", json={"promotions": [good, good]}).status_code
        == 422
    )
    assert owner_client.get("/v1/admin/promotions").status_code == 200
    entries = [(a.actor, a.action, a.subject, a.evidence) for a in ent.store.audit_for("admin")]
    assert entries == [
        ("owner:acc-1", "promotions.written", "admin", {"route": "promotions", "outcome": "200"}),
        ("owner:acc-1", "promotions.written", "admin", {"route": "promotions", "outcome": "422"}),
        ("owner:acc-1", "admin.read", "admin", {"route": "promotions", "outcome": "200"}),
    ]


def test_a_refused_caller_gets_403_and_leaves_no_entry(open_shop, owner_client, ent):
    from tests.admin.test_admin import token

    good = promo(id="offer-2").model_dump(mode="json")
    for headers in ({"Authorization": ""}, {"Authorization": f"Bearer {token('acc-2')}"}):
        assert owner_client.get("/v1/admin/promotions", headers=headers).status_code == 403
        put = owner_client.put("/v1/admin/promotions", headers=headers, json={"promotions": [good]})
        assert put.status_code == 403
    assert ent.store.audit_for("admin") == []
    assert [p.id for p in open_shop.promotions.list()] == ["offer-1"]


def test_an_owner_route_without_an_audit_action_cannot_be_added():
    from fastapi import APIRouter

    from platform_api.commerce.http import _AuditedRoute

    router = APIRouter(route_class=_AuditedRoute)
    with pytest.raises(RuntimeError):

        @router.get("/v1/admin/undeclared")
        def undeclared():
            return {}


def test_an_unknown_field_in_a_promotion_is_refused(open_shop, owner_client):
    good = promo(id="offer-2").model_dump(mode="json")
    r = owner_client.put("/v1/admin/promotions", json={"promotions": [{**good, "colour": "red"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"


def test_without_an_account_link_the_routes_are_not_available(open_shop, signed_in, ent):
    hal, bo = signed_in("hal"), signed_in("bo")
    config = ent.store.get_launch_config()
    ent.store.put_launch_config(config.model_copy(update={"substack_account_url": ""}))
    change = commerce.upgrade_options(hal, START)
    assert [(r.kind, r.available, r.url) for r in change.routes] == [
        ("substack_change_plan", False, None)
    ]
    neither = commerce.upgrade_options(bo, END)
    assert [(r.kind, r.available, r.url) for r in neither.routes] == [
        ("substack", False, None),
        ("platform_only", False, None),
    ]
    assert neither.promotion is None


def test_the_upgrade_route_asks_for_the_terms_first(open_shop, member_client):
    from tests.identity.test_sessions import sign_in

    client, _ = member_client("bo")
    cookie = {"X-Member-Session": sign_in(client, "fay").json()["session"]["cookie"]}
    r = client.get("/v1/me/upgrade-options", headers=cookie)
    assert r.status_code == 409 and r.json()["error"]["code"] == "terms_required"
