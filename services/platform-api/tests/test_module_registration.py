import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from platform_api import cli
from platform_api.app import create_app
from platform_api.settings import Settings


def _probe_router(path: str) -> APIRouter:
    router = APIRouter()

    @router.get(path)
    def probe() -> dict[str, bool]:
        return {"ok": True}

    return router


def test_a_module_route_is_served_in_api_mode_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.library import http as library_http

    monkeypatch.setattr(library_http, "router", _probe_router("/v1/library/probe"))
    assert TestClient(create_app(Settings(app_mode="api"))).get("/v1/library/probe").json() == {
        "ok": True
    }
    assert (
        TestClient(create_app(Settings(app_mode="hooks"))).get("/v1/library/probe").status_code
        == 404
    )


def test_a_module_hook_route_is_served_in_hooks_mode_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.commerce import http as commerce_http

    monkeypatch.setattr(commerce_http, "hooks_router", _probe_router("/hooks/probe"))
    assert TestClient(create_app(Settings(app_mode="hooks"))).get("/hooks/probe").json() == {
        "ok": True
    }
    assert TestClient(create_app(Settings(app_mode="api"))).get("/hooks/probe").status_code == 404


def test_a_job_registered_by_a_module_is_runnable(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.commerce import jobs as commerce_jobs

    monkeypatch.setattr(commerce_jobs, "JOBS", {"probe-job": lambda settings: 7})
    assert cli.build_registry()["probe-job"](Settings()) == 7


def test_the_same_job_name_in_two_modules_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from platform_api.commerce import jobs as commerce_jobs
    from platform_api.library import jobs as library_jobs

    monkeypatch.setattr(commerce_jobs, "JOBS", {"twin": lambda settings: 0})
    monkeypatch.setattr(library_jobs, "JOBS", {"twin": lambda settings: 0})
    with pytest.raises(cli.DuplicateJob) as err:
        cli.build_registry()
    assert "commerce" in str(err.value) and "library" in str(err.value)


def test_the_shared_selfcheck_job_is_registered() -> None:
    assert "selfcheck" in cli.build_registry()


def test_unknown_job_exits_with_status_2_and_lists_known_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["job", "no-such-job"]) == 2
    assert "selfcheck" in capsys.readouterr().err
