from typing import Any

import pytest
from fastapi.testclient import TestClient

from platform_api.app import create_app
from platform_api.settings import Settings
from tests.entitlements.test_campaigns import campaign
from tests.entitlements.test_reconcile import run, state
from tests.fixtures.launch import TERMS


@pytest.fixture
def world(idn: Any, ent: Any) -> TestClient:
    ent.store.put_launch_config(TERMS)
    ent.store.put_campaigns(
        [campaign(), campaign("members", audience="public", grant=None, is_default=True)]
    )
    run(
        ent,
        [
            state("ana", "sub_a"),
            state("hal", "sub_h", grant="status:substack_paid", interval="month"),
        ],
    )
    return TestClient(create_app(Settings()))
