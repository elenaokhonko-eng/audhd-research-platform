"""What a member may see of the library: the shelf and one item, by the access rule (04 §2.3)."""

import math
from datetime import datetime, timedelta
from typing import Literal

from platform_api.entitlements.public import Access, access_for
from platform_api.library.models import ItemCard, ItemDetail, LibraryItem, SignedLink
from platform_api.library.runtime import get_runtime
from platform_api.shared.events import new_event

LINK_TTL = timedelta(seconds=600)
DOWNLOAD_WINDOW = timedelta(hours=1)
DOWNLOAD_LIMIT = 30


class ItemNotFound(Exception):
    pass


class NotEntitled(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TooManyDownloads(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"retry after {retry_after} seconds")
        self.retry_after = retry_after


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


def _find(sku: str, access: Access) -> LibraryItem:
    found = get_runtime().items.get(sku)
    if found is None or found.status == "draft":
        raise ItemNotFound(sku)
    if found.status == "retired" and sku not in access.items:
        raise ItemNotFound(sku)
    return found


def item(sku: str, access: Access) -> ItemDetail:
    found = _find(sku, access)
    return ItemDetail(
        item=card_for(found, access), description=found.abstract, citation=found.citation
    )


def download_link(uid: str, sku: str, now: datetime) -> SignedLink:
    """A 600-second link to the current file; at most 30 per member per hour."""
    runtime = get_runtime()
    access = access_for(uid, now)
    found = _find(sku, access)
    can_open, reason = may_open(found, access)
    if not can_open:
        raise NotEntitled(reason or "purchase_required")
    recent = runtime.downloads.times_since(uid, now - DOWNLOAD_WINDOW)
    if len(recent) >= DOWNLOAD_LIMIT:
        wait = (recent[0] + DOWNLOAD_WINDOW - now).total_seconds()
        raise TooManyDownloads(max(1, math.ceil(wait)))
    url = runtime.files.signed_url(found.file.object, LINK_TTL, now)
    runtime.downloads.add(uid, sku, found.version, now)
    runtime.bus.publish(
        new_event(
            "content.item.downloaded",
            f"library:{sku}",
            {"member_uid": uid, "sku": sku, "version": found.version},
            now=now,
        )
    )
    return SignedLink(url=url, expires_at=now + LINK_TTL)
