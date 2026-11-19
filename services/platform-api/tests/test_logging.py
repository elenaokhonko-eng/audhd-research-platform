import json
import logging

from platform_api.shared.logging import configure_logging


def test_logs_are_json_and_redact_emails(capsys):
    configure_logging("platform-api")
    logging.getLogger("t").warning("hello ada@example.org and bob@example.org")
    line = capsys.readouterr().err.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["severity"] == "WARNING"
    assert data["service"] == "platform-api"
    assert data["message"] == "hello [email] and [email]"
