from fastapi.testclient import TestClient

from platform_api.app import create_app
from platform_api.settings import Settings


def client(mode: str) -> TestClient:
    return TestClient(create_app(Settings(app_mode=mode)))  # type: ignore[arg-type]


def test_health_reports_mode():
    r = client("api").get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "platform-api", "mode": "api", "env": "local"}


def test_api_mode_serves_ping_and_no_hooks():
    c = client("api")
    assert c.get("/v1/ping").json() == {"pong": True}
    assert c.post("/hooks/stripe").status_code == 404


def test_hooks_mode_exposes_no_internal_or_api_routes():
    c = client("hooks")
    assert c.get("/health").status_code == 200
    assert c.get("/v1/ping").status_code == 404
    assert c.post("/internal/pubsub/platform-events").status_code == 404


def test_docs_are_off_outside_local():
    c = TestClient(create_app(Settings(env="prod")))
    assert c.get("/docs").status_code == 404
    assert c.get("/openapi.json").status_code == 404


def test_importing_main_needs_no_cloud_credentials():
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if not k.startswith(("GOOGLE_", "PLATFORM_"))}
    env["PLATFORM_ENV"] = "local"
    result = subprocess.run(
        [sys.executable, "-c", "import platform_api.main"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
