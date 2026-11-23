from datetime import datetime, timedelta

import httpx
import pytest

from platform_api import cli
from platform_api.admin.client import AdminClient, AdminError
from tests.fixtures.people import T0


def client(handler):
    return AdminClient(
        "https://api.example.org",
        lambda: "tok",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_the_client_sends_the_token_and_puts_the_address_in_the_body():
    seen = {}

    def handler(request):
        seen.update(
            url=str(request.url),
            auth=request.headers["authorization"],
            body=request.content.decode(),
        )
        return httpx.Response(200, json={"contact": None})

    assert client(handler).contact_show("ana@example.org") is None
    assert (
        seen["auth"] == "Bearer tok"
        and "@" not in seen["url"]
        and "ana@example.org" in seen["body"]
    )


def test_an_error_body_becomes_an_admin_error():
    with pytest.raises(AdminError) as err:
        client(
            lambda r: httpx.Response(
                403,
                json={
                    "error": {"code": "forbidden", "message": "Not allowed.", "retry_after": None}
                },
            )
        ).launch_report()
    assert (err.value.status, err.value.code) == (403, "forbidden")


def test_launch_set_sends_only_what_was_typed(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(
        cli,
        "admin_client",
        lambda: client(
            lambda r: (
                sent.append(r.content.decode())
                or httpx.Response(
                    200, json={"join_open": True, "library_open": False, "promotions_open": False}
                )
            )
        ),
    )
    assert cli.main(["launch", "set", "--join-open", "true"]) == 0
    assert sent == ['{"join_open":true}'] and "join_open: True" in capsys.readouterr().out


def test_a_refused_command_exits_non_zero_with_plain_words(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "admin_client",
        lambda: client(
            lambda r: httpx.Response(
                403,
                json={
                    "error": {"code": "forbidden", "message": "Not allowed.", "retry_after": None}
                },
            )
        ),
    )
    assert cli.main(["launch", "report"]) == 1 and "Not allowed." in capsys.readouterr().err


# Added by the controller's rulings for this task.


def test_a_non_json_error_is_unknown():
    with pytest.raises(AdminError) as err:
        client(lambda r: httpx.Response(502, text="<html>bad gateway</html>")).support_list()
    assert (err.value.status, err.value.code) == (502, "unknown")


def test_the_client_needs_the_url_and_asks_gcloud_without_a_shell(monkeypatch, capsys):
    monkeypatch.delenv("PLATFORM_API_URL", raising=False)
    assert cli.main(["launch", "report"]) == 1 and "PLATFORM_API_URL" in capsys.readouterr().err
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return cli.subprocess.CompletedProcess(args, 0, stdout="tok\n", stderr="")

    monkeypatch.setenv("PLATFORM_API_URL", "https://api.example.org")
    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli.admin_client()._token() == "tok"
    assert calls == [
        (
            ["gcloud", "auth", "print-identity-token"],
            {"capture_output": True, "text": True, "check": True},
        )
    ]


def test_grant_create_reads_one_line_of_stdin_and_prints_no_address(monkeypatch, capsys):
    import io

    sent = []
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(" ana@example.org \nbo@example.org\n"))
    monkeypatch.setattr(
        cli,
        "admin_client",
        lambda: client(
            lambda r: (
                sent.append(r.content.decode())
                or httpx.Response(200, json={"entitlement_id": "e1"})
            )
        ),
    )
    assert (
        cli.main(
            [
                "grant",
                "create",
                "--email-stdin",
                "--grant",
                "tier:paid",
                "--months",
                "6",
                "--reason",
                "comp",
            ]
        )
        == 0
    )
    assert sent == ['{"email":"ana@example.org","grant":"tier:paid","reason":"comp","months":6}']
    out = capsys.readouterr()
    assert out.out == "entitlement_id: e1\n" and "@" not in out.err


def test_the_client_sends_the_token_for_cloud_run_and_for_the_service():
    seen = {}

    def handler(request):
        seen.update(
            serverless=request.headers.get("x-serverless-authorization"),
            auth=request.headers.get("authorization"),
        )
        return httpx.Response(200, json={"campaigns": [], "members": 0})

    client(handler).launch_report()
    assert seen == {"serverless": "Bearer tok", "auth": "Bearer tok"}


def test_library_publish_prints_one_line_per_item_and_exits_1_on_a_refusal(monkeypatch, capsys):
    calls = []
    report = {
        "dry_run": True,
        "staging_prefix": "batch-1",
        "items": [
            {"sku": "guide-a", "action": "created", "problems": []},
            {"sku": "guide-b", "action": "refused", "problems": ["no file for ana@example.org"]},
        ],
    }

    class Fake:
        def library_publish(self, staging_prefix, dry_run):
            calls.append((staging_prefix, dry_run))
            return report

    monkeypatch.setattr(cli, "admin_client", lambda: Fake())
    code = cli.main(["library", "publish", "--staging-prefix", "batch-1", "--dry-run"])
    assert code == 1 and calls == [("batch-1", True)]
    assert capsys.readouterr().out.splitlines() == [
        "dry_run: true",
        "items: 2",
        "guide-a: created",
        "guide-b: refused",
        "  no file for [email]",
    ]


def test_library_publish_exits_0_when_nothing_was_refused(monkeypatch, capsys):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, request.content.decode()))
        return httpx.Response(
            200,
            json={
                "dry_run": False,
                "staging_prefix": "b",
                "items": [{"sku": "s", "action": "unchanged", "problems": []}],
            },
        )

    monkeypatch.setattr(cli, "admin_client", lambda: client(handler))
    assert cli.main(["library", "publish", "--staging-prefix", "b"]) == 0
    assert calls == [
        (
            "POST",
            "/v1/admin/library/publish",
            '{"staging_prefix":"b","dry_run":false}',
        )
    ]
    assert capsys.readouterr().out == "items: 1\ns: unchanged\n"


def test_library_publish_says_when_nothing_was_found_and_exits_1(monkeypatch, capsys):
    class Fake:
        def library_publish(self, staging_prefix, dry_run):
            return {"dry_run": True, "staging_prefix": staging_prefix, "items": []}

    monkeypatch.setattr(cli, "admin_client", lambda: Fake())
    code = cli.main(["library", "publish", "--staging-prefix", "batch-1", "--dry-run"])
    assert code == 1
    assert capsys.readouterr().out.splitlines() == [
        "dry_run: true",
        "items: 0",
        "nothing found under batch-1/; each item needs its own folder batch-1/<sku>/",
    ]


# Commerce: runs and promotions. Every time is relative to the test clock.

START = T0.isoformat()
END = (T0 + timedelta(minutes=1)).isoformat()
WEEK = (T0 + timedelta(days=7)).isoformat()


def _run(kind="stripe_reconcile", **counts):
    return {
        "run_id": "r1",
        "kind": kind,
        "dry_run": False,
        "state": "completed",
        "guard": "passed",
        "requested_by": "schedule",
        "counts": counts,
        "started_at": START,
        "finished_at": END,
    }


def test_sync_runs_asks_for_a_kind_and_a_limit():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, dict(request.url.params)))
        return httpx.Response(200, json={"runs": [_run()]})

    assert client(handler).sync_runs("roster_import", 5) == [_run()]
    assert client(handler).sync_runs() == [_run()]
    assert seen == [
        ("GET", "/v1/admin/sync-runs", {"kind": "roster_import", "limit": "5"}),
        ("GET", "/v1/admin/sync-runs", {"limit": "20"}),
    ]


def test_promotions_are_put_and_listed():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.content.decode()))
        if request.method == "PUT":
            return httpx.Response(200, json={"written": 1})
        return httpx.Response(200, json={"promotions": [{"id": "p1"}]})

    assert client(handler).promotions_put([{"id": "p1"}]) == 1
    assert client(handler).promotions_list() == [{"id": "p1"}]
    assert seen == [
        ("PUT", "/v1/admin/promotions", '{"promotions":[{"id":"p1"}]}'),
        ("GET", "/v1/admin/promotions", ""),
    ]


def _cli_with(monkeypatch, routes):
    sent = []

    def handler(request):
        sent.append((request.method, request.url.path, request.url.params, request.content))
        return httpx.Response(200, json=routes[(request.method, request.url.path)])

    monkeypatch.setattr(cli, "admin_client", lambda: client(handler))
    return sent


def test_runs_show_prints_one_line_per_run(monkeypatch, capsys):
    reconcile = _run(created=2, updated=0, ended=1, moved=0, unchanged=7, unseen=3, seen=10)
    roster = {**_run("roster_import", no_file=1), "dry_run": True, "state": "failed"}
    roster["guard"] = None
    sent = _cli_with(monkeypatch, {("GET", "/v1/admin/sync-runs"): {"runs": [reconcile, roster]}})
    assert cli.main(["runs", "show", "--kind", "stripe_reconcile", "--limit", "2"]) == 0
    assert dict(sent[0][2]) == {"kind": "stripe_reconcile", "limit": "2"}
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    first, second = lines
    assert first.startswith("run: stripe_reconcile real completed guard=passed")
    assert f"started={START} finished={END}" in first
    assert "created=2 updated=0 ended=1 moved=0 unchanged=7 unseen=3 seen=10" in first
    assert second.startswith("run: roster_import dry_run failed guard=none")
    assert second.endswith("created=0 updated=0 ended=0 moved=0 unchanged=0 unseen=0 no_file=1")


def test_runs_show_refuses_an_unknown_kind(monkeypatch, capsys):
    _cli_with(monkeypatch, {})
    with pytest.raises(SystemExit):
        cli.main(["runs", "show", "--kind", "everything"])


def _promotion(**changes):
    start = T0 + timedelta(days=1)
    body = {
        "id": "offer-1",
        "channel": "substack_offer",
        "audience": ["guests"],
        "plan_interval": "year",
        "starts_at": start,
        "ends_at": start + timedelta(days=7),
        "substack_offer_url": "https://example.org/offer",
        "display": {"title": "An offer"},
    }
    return {**body, **changes}


def _promo_file(tmp_path, promotions):
    import yaml

    path = tmp_path / "promotions.yaml"
    path.write_text(yaml.safe_dump({"promotions": promotions}))
    return str(path)


def test_promo_apply_validates_then_writes(monkeypatch, capsys, tmp_path):
    import json

    sent = _cli_with(monkeypatch, {("PUT", "/v1/admin/promotions"): {"written": 1}})
    assert cli.main(["promo", "apply", "--file", _promo_file(tmp_path, [_promotion()])]) == 0
    [(method, path, _, content)] = sent
    body = json.loads(content)
    assert (method, path) == ("PUT", "/v1/admin/promotions")
    [sent_promotion] = body["promotions"]
    assert sent_promotion["id"] == "offer-1" and "counts" not in sent_promotion
    assert datetime.fromisoformat(sent_promotion["starts_at"]) == T0 + timedelta(days=1)
    assert capsys.readouterr().out == "written: 1\n"


@pytest.mark.parametrize(
    "promotions",
    [
        [_promotion(channel="elsewhere")],
        [_promotion(id="a:b")],
        [_promotion(ends_at=_promotion()["starts_at"])],
        [_promotion(extra="no")],
        "not a list",
    ],
)
def test_promo_apply_refuses_a_file_that_does_not_validate_and_sends_nothing(
    monkeypatch, capsys, tmp_path, promotions
):
    sent = _cli_with(monkeypatch, {})
    assert cli.main(["promo", "apply", "--file", _promo_file(tmp_path, promotions)]) == 1
    assert sent == [] and capsys.readouterr().err.strip()


def test_promo_apply_says_when_the_file_cannot_be_read(monkeypatch, capsys, tmp_path):
    _cli_with(monkeypatch, {})
    assert cli.main(["promo", "apply", "--file", str(tmp_path / "missing.yaml")]) == 1
    assert "YAML" in capsys.readouterr().err


def test_launch_report_also_prints_each_promotion(monkeypatch, capsys):
    promotion = {
        "id": "offer-1",
        "channel": "substack_offer",
        "starts_at": START,
        "ends_at": WEEK,
        "counts": {"upgrades_in_window": 4},
    }
    _cli_with(
        monkeypatch,
        {
            ("GET", "/v1/admin/launch/report"): {"campaigns": [], "members": 3},
            ("GET", "/v1/admin/promotions"): {
                "promotions": [promotion, {**promotion, "id": "o2", "counts": {}}]
            },
        },
    )
    assert cli.main(["launch", "report"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert "members: 3" in out
    assert (
        f"promotion: offer-1 channel=substack_offer window={START}/{WEEK} upgrades_in_window=4"
    ) in out
    assert any(
        line.startswith("promotion: o2 ") and line.endswith("upgrades_in_window=0") for line in out
    )


@pytest.mark.parametrize("limit", ["0", "21", "-1", "many"])
def test_runs_show_takes_a_limit_from_1_to_20(monkeypatch, limit):
    _cli_with(monkeypatch, {})
    with pytest.raises(SystemExit):
        cli.main(["runs", "show", "--limit", limit])


def test_runs_show_accepts_the_largest_limit(monkeypatch):
    sent = _cli_with(monkeypatch, {("GET", "/v1/admin/sync-runs"): {"runs": []}})
    assert cli.main(["runs", "show", "--limit", "20"]) == 0
    assert dict(sent[0][2]) == {"limit": "20"}


@pytest.mark.parametrize(
    "field", [{"counts": {"upgrades_in_window": 1}}, {"updated_at": START}, {"updated_by": "x"}]
)
def test_promo_apply_refuses_the_fields_the_service_writes(monkeypatch, capsys, tmp_path, field):
    sent = _cli_with(monkeypatch, {})
    path = _promo_file(tmp_path, [_promotion(**field)])
    assert cli.main(["promo", "apply", "--file", path]) == 1
    assert sent == []
    assert "counts and update stamps are written by the service" in capsys.readouterr().err


def test_a_cli_error_never_shows_an_address(monkeypatch, capsys, tmp_path):
    _cli_with(monkeypatch, {})
    path = _promo_file(tmp_path, [_promotion(**{"ana@example.org": "x"})])
    assert cli.main(["promo", "apply", "--file", path]) == 1
    err = capsys.readouterr().err
    assert "[email]" in err and "ana@example.org" not in err


def test_the_cli_takes_promotions_from_commerce_public():
    import ast
    from pathlib import Path

    tree = ast.parse(Path(cli.__file__).read_text())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "platform_api.commerce.models" not in modules
    assert "platform_api.commerce.public" in modules
