import pytest

from platform_api.entitlements.access import access_from
from platform_api.library import public as library
from platform_api.library.reading import ItemNotFound, may_open
from tests.fixtures.people import T0, holdings, record
from tests.library.test_publish import run, stage

FREE, PAID = access_from([], T0), access_from(holdings("ana"), T0)
BUYER = access_from([record("bo", "item", grant="item:sample-map")], T0)


def shelf(lib):
    stage(lib, payhip={"url": "https://example.org/buy/sample-map", "product_key": "k"})
    stage(
        lib, sku="sample-guide", title="a guide", kind="guide", file="g.pdf", access="free_members"
    )
    stage(lib, sku="sample-book", title="Zeta book", file="b.pdf", access="purchase_only")
    stage(lib, sku="sample-draft", title="Draft", file="d.pdf", status="draft")
    run("batch-1")


def test_a_free_member_sees_every_card_and_what_is_locked(lib):
    shelf(lib)
    cards = library.catalogue(FREE)
    assert [(c.sku, c.can_open) for c in cards] == [
        ("sample-guide", True),
        ("sample-map", False),
        ("sample-book", False),
    ]
    assert cards[1].buy_url == "https://example.org/buy/sample-map" and cards[2].buy_url is None
    assert "file" not in cards[0].model_dump() and "file_name" not in cards[0].model_dump()


def test_a_paid_member_opens_paid_items_but_not_purchase_only(lib):
    shelf(lib)
    assert {c.sku: c.can_open for c in library.catalogue(PAID)} == {
        "sample-guide": True,
        "sample-map": True,
        "sample-book": False,
    }
    assert all(c.buy_url is None for c in library.catalogue(PAID) if c.can_open)


def test_a_buyer_opens_what_they_bought(lib):
    shelf(lib)
    assert {c.sku: c.can_open for c in library.catalogue(BUYER)}["sample-map"] is True


@pytest.mark.parametrize(
    ("item_access", "access", "expected"),
    [
        ("free_members", FREE, (True, None)),
        ("paid", FREE, (False, "paid_required")),
        ("paid", PAID, (True, None)),
        ("purchase_only", PAID, (False, "purchase_required")),
        ("purchase_only", FREE, (False, "purchase_required")),
    ],
)
def test_the_access_rule(lib, item_access, access, expected):
    stage(lib, access=item_access)
    run("batch-1")
    assert may_open(lib.items.get("sample-map"), access) == expected


def test_item_detail_and_what_cannot_be_found(lib):
    shelf(lib)
    detail = library.item("sample-map", FREE)
    assert (detail.item.sku, detail.description, detail.item.can_open) == (
        "sample-map",
        "An invented item.",
        False,
    )
    for sku in ("sample-draft", "nope"):
        with pytest.raises(ItemNotFound):
            library.item(sku, PAID)


def test_a_retired_item_leaves_the_catalogue_but_stays_with_its_buyer(lib):
    shelf(lib)
    stage(lib, prefix="batch-2", status="retired")
    run("batch-2")
    assert "sample-map" not in [c.sku for c in library.catalogue(PAID)]
    assert library.item("sample-map", BUYER).item.can_open is True
    with pytest.raises(ItemNotFound):
        library.item("sample-map", PAID)
