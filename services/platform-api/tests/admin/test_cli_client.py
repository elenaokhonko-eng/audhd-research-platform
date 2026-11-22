import httpx
import pytest

from platform_api import cli
from platform_api.admin.client import AdminClient, AdminError


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
