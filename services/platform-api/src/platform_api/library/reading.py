"""What a member may see of the library: the shelf and one item, by the access rule (04 §2.3)."""

from typing import Literal

from platform_api.entitlements.public import Access
from platform_api.library.models import ItemCard, ItemDetail, LibraryItem
from platform_api.library.runtime import get_runtime


class ItemNotFound(Exception):
    pass


def may_open(
    item: LibraryItem, access: Access
) -> tuple[bool, Literal["paid_required", "purchase_required"] | None]:
    if item.access == "free_members" or item.sku in access.items:
        return True, None
    if item.access == "paid":
        return (True, None) if access.tier == "paid" else (False, "paid_required")
    return False, "purchase_required"


def card_for(item: LibraryItem, access: Access) -> ItemCard:
    can_open, _ = may_open(item, access)
    buy_url = None if can_open or item.payhip is None else item.payhip.get("url")
    return ItemCard(
        sku=item.sku,
        title=item.title,
        kind=item.kind,
        abstract=item.abstract,
        version=item.version,
        pages=item.pages,
        access=item.access,
        can_open=can_open,
        buy_url=buy_url,
    )


def catalogue(access: Access) -> list[ItemCard]:
    shelf = [i for i in get_runtime().items.list_all() if i.status == "published"]
    shelf.sort(key=lambda i: (i.title.casefold(), i.sku))
    return [card_for(i, access) for i in shelf]


def item(sku: str, access: Access) -> ItemDetail:
    found = get_runtime().items.get(sku)
    if found is None or found.status == "draft":
        raise ItemNotFound(sku)
    if found.status == "retired" and sku not in access.items:
        raise ItemNotFound(sku)
    return ItemDetail(
        item=card_for(found, access), description=found.abstract, citation=found.citation
    )
