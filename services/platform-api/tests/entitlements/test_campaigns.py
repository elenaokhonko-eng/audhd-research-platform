from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from platform_api.app import create_app
from platform_api.entitlements import public as ent_api
from platform_api.entitlements.campaigns import campaign_state, grants_from
from platform_api.entitlements.models import Campaign, ChannelsPatch, GrantPolicy, LaunchConfig
from platform_api.settings import Settings
from platform_api.shared.clock import add_months
from tests.fixtures.people import CUT_OFF, EMAIL, T0, holdings, record

POLICY = GrantPolicy(
    grant="tier:paid",
    months=6,
    starts="at_claim",
    fixed_until=None,
    requires_live_source=["substack_stripe", "substack_roster"],
    paid_since_before=CUT_OFF,
    plan_intervals=["year"],
)
OPEN = LaunchConfig(join_open=True)
WIDE = POLICY.model_copy(update={"paid_since_before": None, "plan_intervals": None})


def campaign(slug="founding", **over):
    base = dict(
        slug=slug,
        audience="substack_paid",
        opens_at=T0 - timedelta(days=1),
        closes_at=T0 + timedelta(days=60),
        is_default=False,
        grant=POLICY,
        copy={"headline": "h", "body": "b", "cta": "c"},
        counts={},
    )
    return Campaign(**{**base, **over})


def due(name, held=None, c=None, config=OPEN, now=T0):
    return grants_from(
        held if held is not None else holdings(name)[:1], [c or campaign()], config, now
    )


def test_ana_gets_six_months_from_the_moment_of_the_claim():
    [spec] = due("ana")
    assert (spec.campaign, spec.grant, spec.valid_until) == (
        "founding",
        "tier:paid",
        add_months(T0, 6),
    )


@pytest.mark.parametrize("name", ["bo", "cy", "di", "hal"])
def test_free_late_no_interval_and_monthly_readers_get_none(name):
    assert due(name, held=holdings(name)) == []


def test_gus_gets_exactly_one_from_two_qualifying_records():
    assert len(due("gus", held=holdings("gus"), c=campaign(grant=WIDE))) == 1


def test_evaluating_again_after_the_grant_exists_gives_nothing_even_when_it_has_ended():
    held = holdings("fay")  # cancelled subscription + launch grant
    assert due("fay", held=held) == []
    ended = [e.model_copy(update={"status": "expired"}) for e in holdings("ana")]
    live_again = [record("ana", "stripe_year"), ended[1]]
    assert due("ana", held=live_again) == []


@pytest.mark.parametrize(
    ("over", "config", "now", "state"),
    [
        ({}, LaunchConfig(join_open=False), T0, "closed"),
        ({"opens_at": T0 + timedelta(days=1)}, OPEN, T0, "scheduled"),
        ({}, OPEN, T0 + timedelta(days=61), "closed"),
    ],
)
def test_a_campaign_that_is_not_open_grants_nothing(over, config, now, state):
    c = campaign(**over)
    assert campaign_state(c, config, now) == state and due("ana", c=c, config=config, now=now) == []


def test_a_policy_without_cut_off_or_intervals_takes_every_paying_reader():
    wide = campaign(grant=WIDE)
    assert [len(due(n, held=holdings(n), c=wide)) for n in ("cy", "di", "hal")] == [1, 1, 1]


def test_applying_twice_creates_one_grant_and_only_for_a_member(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns(
        [campaign(), campaign("members", audience="public", grant=None, is_default=True)]
    )
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch())
    ent.store.write(
        cid, [e.model_copy(update={"contact_id": cid}) for e in holdings("ana")[:1]], []
    )
    assert ent_api.apply_grant_policies(cid, T0) == []  # nobody has signed in
    ent_api.claim_for_member("u-ana", cid)
    first, second = (
        ent_api.apply_grant_policies(cid, T0),
        ent_api.apply_grant_policies(cid, T0 + timedelta(days=3)),
    )
    assert len(first) == 1 and second == []
    stored = ent.store.get_entitlement(first[0])
    assert (stored.source, stored.source_ref, stored.valid_until, stored.member_uid) == (
        "grant",
        "campaign:founding",
        add_months(T0, 6),
        "u-ana",
    )
    assert ent.store.audit_for(first[0])[0].evidence["entitlement_id"]
    assert ent.store.get_campaign("founding").counts["grants_created"] == 1


def test_an_unknown_slug_falls_back_to_the_default_campaign(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns(
        [campaign(), campaign("members", audience="public", grant=None, is_default=True)]
    )
    assert (
        ent_api.campaign_by_slug("nope", T0).slug == "members"
        and ent_api.campaign_by_slug(None, T0).slug == "members"
    )
    body = TestClient(create_app(Settings())).get("/v1/public/campaigns/nope").json()
    assert (body["slug"], body["state"], body["audience"]) == (None, "open", "public")
    assert (
        TestClient(create_app(Settings())).get("/v1/public/campaigns/founding").json()["slug"]
        == "founding"
    )


def test_an_arrival_is_counted_and_published_without_an_address(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign()])
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    ent_api.record_arrival("u-ana", ent.store.get_campaign("founding"), "paid")
    assert ent.store.get_campaign("founding").counts == {"arrivals": 1, "recognised_paid": 1}
    assert ent.store.get_contact(cid).invite == {"campaign": "founding", "state": "accepted"}
    [event] = [e for e in ent.bus.published if e.type.endswith("membership.campaign.joined")]
    assert event.data == {
        "member_uid": "u-ana",
        "contact_id": cid,
        "campaign": "founding",
        "recognition": "paid",
    }


# Controller rulings for Task 5, beyond the brief's tests.


@pytest.mark.parametrize("slug", ["default", "Founding", "a" * 41, "", "spring\n", "x y"])
def test_a_slug_outside_the_pattern_or_reserved_is_refused(slug):
    with pytest.raises(ValidationError):
        campaign(slug=slug)


@pytest.mark.parametrize(
    "update",
    [
        {"months": None},
        {"starts": "fixed", "fixed_until": None},
        {"requires_live_source": ["substack_stripe", "grant"]},
    ],
)
def test_an_incomplete_policy_or_one_a_grant_could_satisfy_is_refused(update):
    with pytest.raises(ValidationError):
        GrantPolicy.model_validate({**POLICY.model_dump(), **update})


def test_a_second_evaluation_that_loses_the_race_creates_and_counts_nothing(ent, monkeypatch):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign()])
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    ent.store.write(
        cid, [e.model_copy(update={"contact_id": cid}) for e in holdings("ana")[:1]], []
    )
    monkeypatch.setattr(ent.store, "create_if_absent", lambda entitlement, audit: False)
    assert ent_api.apply_grant_policies(cid, T0) == []
    assert ent.store.get_campaign("founding").counts == {}
    assert not [e for e in ent.bus.published if e.type.endswith("entitlement.granted")]


def test_a_launch_grant_is_announced_like_an_owner_grant(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign()])
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    ent.store.write(
        cid, [e.model_copy(update={"contact_id": cid}) for e in holdings("ana")[:1]], []
    )
    [gid] = ent_api.apply_grant_policies(cid, T0)
    stored = ent.store.get_entitlement(gid)
    assert (stored.access_scope, stored.updated_by, stored.valid_from) == (
        "platform_only",
        "policy:founding",
        T0,
    )
    [event] = [e for e in ent.bus.published if e.type.endswith("entitlement.granted")]
    assert event.data == {
        "contact_id": cid,
        "entitlement_id": gid,
        "grant": "tier:paid",
        "source": "grant",
        "source_ref": "campaign:founding",
        "access_scope": "platform_only",
    }
    assert not [e for e in ent.bus.published if e.type.endswith("tier.changed")]


def test_a_free_arrival_counts_only_the_arrival_and_a_stranger_is_refused(ent):
    ent.store.put_campaigns([campaign()])
    ent_api.upsert_contact(EMAIL["bo"], ChannelsPatch(platform={"member_uid": "u-bo"}))
    ent_api.record_arrival("u-bo", ent.store.get_campaign("founding"), "free")
    assert ent.store.get_campaign("founding").counts == {"arrivals": 1}
    with pytest.raises(LookupError) as raised:
        ent_api.record_arrival("u-nobody", ent.store.get_campaign("founding"), "free")
    assert "@" not in str(raised.value)


def test_no_default_campaign_is_a_not_found(ent):
    ent.store.put_campaigns([campaign()])
    with pytest.raises(LookupError):
        ent_api.campaign_by_slug("nope", T0)
    response = TestClient(create_app(Settings())).get("/v1/public/campaigns/nope")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found")


def test_the_launch_switches_refuse_unknown_keys_and_audit_a_change(ent):
    with pytest.raises(ValueError, match="unknown"):
        ent_api.update_launch_config({"join_open": True, "surprise": 1}, "owner:acc-1")
    assert ent_api.launch_config() == LaunchConfig()
    config = ent_api.update_launch_config({"join_open": True}, "owner:acc-1")
    assert config.join_open and ent_api.launch_config().join_open
    [entry] = ent_api.audit_for("config/launch")
    assert (entry.action, entry.actor) == ("launch.switched", "owner:acc-1")


def test_writing_campaigns_again_keeps_their_counts(ent):
    ent.store.put_campaigns([campaign(counts={"arrivals": 4})])
    assert ent_api.put_campaigns([campaign(), campaign("spring")], "owner:acc-1") == 2
    assert {c.slug: c.counts for c in ent_api.list_campaigns()} == {
        "founding": {"arrivals": 4},
        "spring": {},
    }


def test_the_owner_sees_a_contact_with_reasons_and_audit_but_no_address(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign()])
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    ent.store.write(
        cid, [e.model_copy(update={"contact_id": cid}) for e in holdings("ana")[:1]], []
    )
    [gid] = ent_api.apply_grant_policies(cid, T0)
    view = ent_api.contact_view(cid, T0)
    assert view.has_member and gid in {r.entitlement_id for r in view.reasons}
    assert [a.subject for a in view.audit] == [gid]
    assert "@" not in view.model_dump_json() and ent_api.contact_view("missing", T0) is None


def test_the_cut_off_alone_keeps_out_a_reader_who_started_paying_after_it():
    late_ok = campaign(grant=POLICY.model_copy(update={"plan_intervals": None}))
    assert [len(due(n, held=holdings(n), c=late_ok)) for n in ("cy", "hal")] == [0, 1]


@pytest.mark.parametrize("slug", ["..", "__x__", "A B", "a" * 41])
def test_a_slug_outside_the_pattern_is_never_looked_up(ent, slug):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns(
        [campaign(), campaign("members", audience="public", grant=None, is_default=True)]
    )
    asked = []
    get_campaign = ent.store.get_campaign

    def spy(name):
        asked.append(name)
        return get_campaign(name)

    ent.store.get_campaign = spy
    assert ent_api.campaign_by_slug(slug, T0).slug == "members" and asked == []
    if slug != "..":  # ".." is folded into the path by the client before it is sent
        body = TestClient(create_app(Settings())).get(f"/v1/public/campaigns/{slug}").json()
        assert (body["slug"], body["audience"]) == (None, "public") and asked == []


def test_put_campaigns_refuses_a_repeated_slug_and_a_second_default(ent):
    default = campaign("members", audience="public", grant=None, is_default=True)
    with pytest.raises(ValueError):
        ent_api.put_campaigns([campaign(), campaign()], "owner:acc-1")
    ent_api.put_campaigns([campaign(), default], "owner:acc-1")
    with pytest.raises(ValueError):  # "members" stays stored and stays the default
        ent_api.put_campaigns([campaign("other", is_default=True)], "owner:acc-1")
    assert [c.slug for c in ent_api.list_campaigns() if c.is_default] == ["members"]
    assert ent.store.get_campaign("other") is None
