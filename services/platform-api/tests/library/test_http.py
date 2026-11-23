from platform_api.entitlements.models import LaunchConfig
from tests.library.test_catalogue import shelf


def test_the_catalogue_and_a_download_for_a_paid_member(lib, ent, member_client):
    shelf(lib)
    client, cookie = member_client("ana")
    items = client.get("/v1/library/items", headers=cookie).json()["items"]
    assert {i["sku"]: i["can_open"] for i in items}["sample-map"] is True
    link = client.post("/v1/library/items/sample-map/download", headers=cookie)
    assert link.status_code == 200 and set(link.json()) == {"url", "expires_at"}


def test_a_free_member_is_told_why(lib, ent, member_client):
    shelf(lib)
    client, cookie = member_client("bo")
    r = client.post("/v1/library/items/sample-map/download", headers=cookie)
    assert r.status_code == 403 and r.json()["error"] == {
        "code": "forbidden",
        "message": r.json()["error"]["message"],
        "retry_after": None,
        "reason": "paid_required",
    }


def test_unknown_and_malformed_skus_are_not_found(lib, ent, member_client):
    shelf(lib)
    client, cookie = member_client("ana")
    assert client.get("/v1/library/items/sample-map", headers=cookie).status_code == 200
    for sku in ("nope", "Sample-Map", "a" * 80, "x..y"):
        assert client.get(f"/v1/library/items/{sku}", headers=cookie).status_code == 404
        assert client.post(f"/v1/library/items/{sku}/download", headers=cookie).status_code == 404


def test_the_switch_closes_the_member_routes_but_not_publishing(
    lib, ent, member_client, owner_client
):
    shelf(lib)
    client, cookie = member_client("ana")
    ent.store.put_launch_config(
        LaunchConfig(
            join_open=True,
            library_open=False,
            required_terms_version="t1",
            required_privacy_version="p1",
        )
    )
    assert client.get("/v1/library/items", headers=cookie).status_code == 404
    report = owner_client.post(
        "/v1/admin/library/publish", json={"staging_prefix": "batch-1", "dry_run": True}
    )
    assert report.status_code == 200 and report.json()["dry_run"] is True
    assert (
        owner_client.post(
            "/v1/admin/library/publish", json={"staging_prefix": "items/x", "dry_run": True}
        ).status_code
        == 422
    )


def test_the_routes_need_a_member_and_accepted_terms(lib, ent, member_client):
    client, cookie = member_client("ana")
    assert client.get("/v1/library/items").status_code == 401
    ent.store.put_launch_config(
        LaunchConfig(
            join_open=True,
            library_open=True,
            required_terms_version="t2",
            required_privacy_version="p1",
        )
    )
    assert client.get("/v1/library/items", headers=cookie).status_code == 409


def test_every_publish_call_by_the_owner_is_audited(lib, ent, owner_client):
    shelf(lib)
    calls = [
        {"staging_prefix": "batch-1", "dry_run": True},
        {"staging_prefix": "items/x", "dry_run": False},
        {"staging_prefix": "batch-1", "dry_run": True, "extra": 1},
    ]
    assert [owner_client.post("/v1/admin/library/publish", json=c).status_code for c in calls] == [
        200,
        422,
        422,
    ]
    malformed = owner_client.post("/v1/admin/library/publish", content=b"[1")
    assert malformed.status_code == 422 and "[1" not in malformed.text
    audit = [
        (a.actor, a.subject, a.action, a.evidence["outcome"])
        for a in ent.store.audit_for("admin")
        if a.evidence.get("route") == "library/publish"
    ]
    assert audit == [
        ("owner:acc-1", "admin", "library.dry_run", "200"),
        ("owner:acc-1", "admin", "library.published", "422"),
        ("owner:acc-1", "admin", "library.dry_run", "422"),
        ("owner:acc-1", "admin", "library.published", "422"),
    ]
