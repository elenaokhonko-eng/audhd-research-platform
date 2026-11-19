import json
import logging
import re
import sys

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class _JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        message = _EMAIL.sub("[email]", record.getMessage())
        if record.exc_info:
            message = f"{message} {_EMAIL.sub('[email]', self.formatException(record.exc_info))}"
        return json.dumps(
            {"severity": record.levelname, "message": message, "service": self._service}
        )


def configure_logging(service: str) -> None:
    """One JSON object per line on stderr; email-shaped text becomes [email]."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
