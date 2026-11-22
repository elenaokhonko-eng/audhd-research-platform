import logging

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import ChannelsPatch, entitlement_id, normalise_email
from tests.fixtures.people import EMAIL


def test_one_person_one_contact_whatever_the_spelling(ent):
    assert ent_api.contact_id_for(" Ana@Example.ORG ") == ent_api.contact_id_for(EMAIL["ana"])
    assert len(ent_api.contact_id_for(EMAIL["ana"])) == 32
    assert ent_api.contact_id_for(EMAIL["ana"]) != ent_api.contact_id_for(EMAIL["bo"])


@pytest.mark.parametrize("bad", ["", "ana", "@example.org", "ana@", "a@b@c"])
def test_a_value_that_is_not_an_address_is_refused_without_being_repeated(bad):
    with pytest.raises(ValueError) as err:
        normalise_email(bad)
    assert bad == "" or bad not in str(err.value)


def test_upsert_keeps_the_first_address_and_merges_channels(ent):
    cid = ent_api.upsert_contact(
        "Ana@Example.org", ChannelsPatch(stripe={"has_substack_subscription": True})
    )
    again = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    contact = ent.store.get_contact(cid)
    assert again == cid and contact.email == "Ana@Example.org" and contact.key_version == "local"
    assert contact.channels["stripe"] == {"has_substack_subscription": True}
    assert ent.store.contact_ids_for_member("u-ana") == [cid]


def test_a_contact_never_prints_its_address(ent, caplog):
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch())
    with caplog.at_level(logging.INFO):
        logging.getLogger("t").info(
            "contact %r %s", ent.store.get_contact(cid), ent.store.get_contact(cid)
        )
    assert "@" not in caplog.text


def test_entitlement_ids_are_deterministic_and_separate_people():
    a = entitlement_id("substack_stripe", "sub_1", "c1", "tier:paid")
    assert a == entitlement_id("substack_stripe", "sub_1", "c1", "tier:paid") and len(a) == 32
    assert a != entitlement_id("substack_stripe", "sub_1", "c2", "tier:paid")
