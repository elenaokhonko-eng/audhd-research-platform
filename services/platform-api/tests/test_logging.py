import json
import logging
import sys

import pytest

from platform_api.shared.logging import configure_logging


@pytest.fixture(autouse=True)
def _restore(restore_root_logger: None) -> None:
    return None


def test_logs_are_json_and_redact_emails(capsys):
    configure_logging("platform-api")
    logging.getLogger("t").warning("hello ana@example.org and bo@example.org")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["severity"] == "WARNING"
    assert data["service"] == "platform-api"
    assert data["message"] == "hello [email] and [email]"


def test_uvicorn_loggers_use_the_json_handler(capsys):
    # Uvicorn installs its own handlers and stops propagation; mimic that.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.addHandler(logging.StreamHandler(sys.stdout))
        lg.propagate = False
    configure_logging("platform-api")
    logging.getLogger("uvicorn.access").info("GET /x for ana@example.org")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["message"] == "GET /x for [email]"
    assert data["severity"] == "INFO"
