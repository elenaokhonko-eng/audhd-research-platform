import base64
import json

import pytest
from fastapi.testclient import TestClient

from platform_api.app import Deps, create_app
from platform_api.settings import Settings
from platform_api.shared.auth import NotAuthorised, PushIdentity
from platform_api.shared.events import new_event
from platform_api.shared.handlers import HandlerRegistry
from platform_api.shared.inbox import InMemoryInbox

URL = "/internal/pubsub/platform-events"
GOOD = {"Authorization": "Bearer good"}


def verify(token: str) -> PushIdentity:
    if token == "good":  # noqa: S105
        return PushIdentity(email="pubsub-push@test.iam.gserviceaccount.com")
    if token == "other-sa":  # noqa: S105
        raise NotAuthorised("wrong_identity")
    raise NotAuthorised("invalid")


def envelope(event) -> dict:
    data = base64.b64encode(event.model_dump_json().encode()).decode()
    return {"message": {"data": data, "messageId": "1"}, "subscription": "s"}


@pytest.fixture
def setup():
    calls: list[str] = []
    registry = HandlerRegistry()
    inbox = InMemoryInbox()
    app = create_app(Settings(), Deps(bus=None, inbox=inbox, registry=registry, verify_push=verify))
    return TestClient(app, raise_server_exceptions=False), registry, inbox, calls


def test_rejects_missing_and_invalid_tokens(setup):
    c, *_ = setup
    assert c.post(URL, json={}).status_code == 401
    assert c.post(URL, json={}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_rejects_a_valid_token_from_another_service_account(setup):
    c, *_ = setup
    assert c.post(URL, json={}, headers={"Authorization": "Bearer other-sa"}).status_code == 403


def test_duplicate_delivery_runs_the_handler_once(setup):
    c, registry, inbox, calls = setup
    registry.register("x.y.happened", lambda e: calls.append(e.id))
    body = envelope(new_event("x.y.happened", "s", {}, event_id="e1"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert calls == ["e1"]
    assert inbox.seen("e1")


def test_failing_handler_returns_500_and_is_retried(setup):
    c, registry, inbox, calls = setup
    attempts = {"n": 0}

    def flaky(e):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("boom")
        calls.append(e.id)

    registry.register("x.y.happened", flaky)
    body = envelope(new_event("x.y.happened", "s", {}, event_id="e2"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 500
    assert not inbox.seen("e2")
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert calls == ["e2"]


def test_unknown_type_is_recorded_and_acknowledged(setup):
    c, _, inbox, _ = setup
    body = envelope(new_event("nobody.listens.here", "s", {}, event_id="e3"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert inbox.seen("e3")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": {"data": "not-base64!"}},
        {"message": {"data": base64.b64encode(b"{}").decode()}},
    ],
)
def test_malformed_messages_are_acknowledged_not_retried(setup, body):
    c, *_ = setup
    assert c.post(URL, json=body, headers=GOOD).status_code == 204


def test_hooks_mode_never_mounts_the_receiver_even_with_dependencies():
    deps = Deps(bus=None, inbox=InMemoryInbox(), registry=HandlerRegistry(), verify_push=verify)
    c = TestClient(create_app(Settings(app_mode="hooks"), deps))
    assert c.post(URL, json={}, headers=GOOD).status_code == 404


# Additions beyond the brief.


@pytest.mark.parametrize(
    "headers",
    [{"Authorization": "Basic good"}, {"Authorization": "Bearer "}, {"Authorization": "Bearer"}],
)
def test_bad_authorization_header_shapes_are_401(setup, headers):
    c, *_ = setup
    assert c.post(URL, json={}, headers=headers).status_code == 401


def test_router_not_mounted_without_all_dependencies():
    deps = Deps(inbox=InMemoryInbox(), registry=HandlerRegistry())
    c = TestClient(create_app(Settings(), deps))
    assert c.post(URL, json={}, headers=GOOD).status_code == 404


def test_handler_error_response_does_not_leak_exception_text(setup):
    c, registry, inbox, _ = setup

    def boom(e):
        raise RuntimeError("secret-detail")

    registry.register("x.y.happened", boom)
    body = envelope(new_event("x.y.happened", "s", {}, event_id="e4"))
    r = c.post(URL, json=body, headers=GOOD)
    assert r.status_code == 500
    assert "secret-detail" not in r.text


def test_malformed_message_log_carries_no_payload(setup, caplog):
    c, *_ = setup
    payload = base64.b64encode(b'{"who": "ana@example.org"}').decode()
    with caplog.at_level("ERROR"):
        r = c.post(URL, json={"message": {"data": payload}}, headers=GOOD)
    assert r.status_code == 204
    assert any(rec.levelname == "ERROR" for rec in caplog.records)
    assert "ana@example.org" not in caplog.text
    assert payload not in caplog.text


def test_non_object_json_body_is_acknowledged(setup):
    c, *_ = setup
    assert c.post(URL, json=[1, 2], headers=GOOD).status_code == 204


# push_identity_from_token


def _jwt(claims: dict) -> str:
    def seg(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.sig"


SA = "pubsub-push@test.iam.gserviceaccount.com"


def test_identity_good_token():
    from platform_api.shared.auth import push_identity_from_token

    t = _jwt({"email": SA, "email_verified": True})
    assert push_identity_from_token(t, allowed_email=SA) == PushIdentity(email=SA)


def test_identity_wrong_email():
    from platform_api.shared.auth import push_identity_from_token

    t = _jwt({"email": "other@test.iam.gserviceaccount.com", "email_verified": True})
    with pytest.raises(NotAuthorised) as e:
        push_identity_from_token(t, allowed_email=SA)
    assert e.value.reason == "wrong_identity"


@pytest.mark.parametrize(
    "claims",
    [
        {"email": SA},
        {"email": SA, "email_verified": False},
        {"email_verified": True},
        {"email": ""},
    ],
)
def test_identity_unverified_or_missing_email_is_invalid(claims):
    from platform_api.shared.auth import push_identity_from_token

    with pytest.raises(NotAuthorised) as e:
        push_identity_from_token(_jwt(claims), allowed_email=SA)
    assert e.value.reason == "invalid"


@pytest.mark.parametrize("token", ["garbage", "a.b.c", "", "....", "e30.W10.x"])
def test_identity_garbage_is_invalid(token):
    from platform_api.shared.auth import push_identity_from_token

    with pytest.raises(NotAuthorised) as e:
        push_identity_from_token(token, allowed_email=SA)
    assert e.value.reason == "invalid"


def test_identity_empty_allowed_email_never_matches():
    from platform_api.shared.auth import push_identity_from_token

    t = _jwt({"email": "", "email_verified": True})
    with pytest.raises(NotAuthorised):
        push_identity_from_token(t, allowed_email="")
    t = _jwt({"email": SA, "email_verified": True})
    with pytest.raises(NotAuthorised) as e:
        push_identity_from_token(t, allowed_email="")
    assert e.value.reason == "wrong_identity"


def test_handlers_run_off_the_event_loop(setup):
    import asyncio

    c, registry, _inbox, _calls = setup
    off_loop: list[bool] = []

    def handler(e):
        try:
            asyncio.get_running_loop()
            off_loop.append(False)
        except RuntimeError:
            off_loop.append(True)

    registry.register("x.y.happened", handler)
    body = envelope(new_event("x.y.happened", "s", {}, event_id="e-thread"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert off_loop == [True]
