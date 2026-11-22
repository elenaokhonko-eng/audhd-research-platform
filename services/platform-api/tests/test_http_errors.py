from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from platform_api.app import create_app
from platform_api.settings import Settings
from platform_api.shared.http import ApiError


class Body(BaseModel):
    note: str


def client():
    app = create_app(Settings())
    extra = APIRouter()

    @extra.get("/v1/_boom")
    def boom():
        raise ApiError(429, "rate_limited", "Try again later.", retry_after=30)

    @extra.post("/v1/_body")
    def body(b: Body):
        return {}

    app.include_router(extra)
    return TestClient(app)


def test_an_api_error_has_the_contract_shape():
    r = client().get("/v1/_boom")
    assert r.status_code == 429
    assert r.json() == {
        "error": {"code": "rate_limited", "message": "Try again later.", "retry_after": 30}
    }


def test_a_bad_body_is_validation_failed_and_does_not_echo_values():
    r = client().post("/v1/_body", json={"note": {"secret": "ana@example.org"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    assert "@" not in r.text and "note" in r.json()["error"]["message"]


def test_unknown_route_and_wrong_method_have_the_contract_shape():
    c = client()
    r = c.get("/v1/nowhere")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    assert r.json()["error"]["retry_after"] is None
    r = c.post("/health")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"


def test_an_unhandled_exception_is_a_500_without_its_text():
    app = create_app(Settings())

    @app.get("/v1/_crash")
    def crash():
        raise RuntimeError("ana@example.org")

    r = TestClient(app, raise_server_exceptions=False).get("/v1/_crash")
    assert r.status_code == 500 and "@" not in r.text
    assert r.json()["error"]["code"] == "internal_error"
