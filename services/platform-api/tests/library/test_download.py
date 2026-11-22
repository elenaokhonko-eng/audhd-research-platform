from datetime import timedelta

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import ChannelsPatch
from platform_api.library import public as library
from platform_api.library.reading import ItemNotFound, NotEntitled, TooManyDownloads
from tests.fixtures.people import EMAIL, T0, record
from tests.library.test_catalogue import shelf
from tests.library.test_publish import PDF, run, stage


def member(ent, name, *kinds, **over):
    cid = ent_api.upsert_contact(EMAIL[name], ChannelsPatch(platform={"member_uid": f"u-{name}"}))
    ent.store.write(
        cid, [record(name, k, contact_id=cid, member_uid=f"u-{name}", **over) for k in kinds], []
    )
    return f"u-{name}"


def test_a_paid_member_gets_a_ten_minute_link_and_the_download_is_recorded(lib, ent):
    shelf(lib)
    link = library.download_link(member(ent, "ana", "stripe_year"), "sample-map", T0)
    assert (
        link.expires_at == T0 + timedelta(seconds=600)
        and "items/sample-map/1.0/sample-map-v1.0.pdf" in link.url
    )
    assert len(lib.downloads.times_since("u-ana", T0 - timedelta(hours=1))) == 1
    [event] = [e for e in ent.bus.published if e.type.endswith("content.item.downloaded")]
    assert event.data == {"member_uid": "u-ana", "sku": "sample-map", "version": "1.0"}


def test_a_free_member_is_refused_with_the_reason(lib, ent):
    shelf(lib)
    uid = member(ent, "bo")
    with pytest.raises(NotEntitled) as paid:
        library.download_link(uid, "sample-map", T0)
    with pytest.raises(NotEntitled) as bought:
        library.download_link(uid, "sample-book", T0)
    assert (paid.value.reason, bought.value.reason) == ("paid_required", "purchase_required")
    assert (
        library.download_link(uid, "sample-guide", T0).url
        and len(lib.downloads.times_since(uid, T0 - timedelta(hours=1))) == 1
    )


def test_the_link_is_for_the_current_version(lib, ent):
    shelf(lib)
    stage(lib, prefix="batch-2", pdf=PDF + b"2", version="1.1", file="sample-map-v1.1.pdf")
    run("batch-2")
    assert (
        "items/sample-map/1.1/"
        in library.download_link(member(ent, "ana", "stripe_year"), "sample-map", T0).url
    )


def test_a_retired_item_stays_open_to_its_buyer_only(lib, ent):
    shelf(lib)
    stage(lib, prefix="batch-2", status="retired")
    run("batch-2")
    assert library.download_link(
        member(ent, "bo", "item", grant="item:sample-map"), "sample-map", T0
    ).url
    with pytest.raises(ItemNotFound):
        library.download_link(member(ent, "ana", "stripe_year"), "sample-map", T0)


def test_a_grant_that_has_ended_no_longer_opens_paid_items(lib, ent):
    shelf(lib)
    uid = member(ent, "fay", "launch_grant", valid_until=T0 + timedelta(days=1))
    assert library.download_link(uid, "sample-map", T0).url
    with pytest.raises(NotEntitled):
        library.download_link(uid, "sample-map", T0 + timedelta(days=2))


def test_the_thirty_first_download_in_an_hour_is_refused(lib, ent):
    shelf(lib)
    uid = member(ent, "ana", "stripe_year")
    for i in range(30):
        library.download_link(uid, "sample-guide", T0 + timedelta(seconds=i))
    with pytest.raises(TooManyDownloads) as err:
        library.download_link(uid, "sample-guide", T0 + timedelta(minutes=10))
    assert err.value.retry_after == 3000
    assert library.download_link(uid, "sample-guide", T0 + timedelta(hours=1, seconds=1)).url
