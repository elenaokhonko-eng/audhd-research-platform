import logging
from collections.abc import Iterator

import pytest


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    """Put the root logger and uvicorn loggers back after a test reconfigures them."""
    names = ["", "uvicorn", "uvicorn.error", "uvicorn.access"]
    saved = [(lg, lg.handlers[:], lg.level, lg.propagate) for lg in map(logging.getLogger, names)]
    yield
    for lg, handlers, level, propagate in saved:
        lg.handlers[:] = handlers
        lg.setLevel(level)
        lg.propagate = propagate
