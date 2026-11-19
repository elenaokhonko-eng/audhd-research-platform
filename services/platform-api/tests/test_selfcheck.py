import pytest

from platform_api.jobs.selfcheck import run_selfcheck
from platform_api.shared.bus import InMemoryBus


def test_selfcheck_publishes_one_event_and_prints_its_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    bus = InMemoryBus()
    event_id = run_selfcheck(bus)
    assert [e.type for e in bus.published] == ["org.audhdneurobiology.platform.selfcheck.ran"]
    assert bus.published[0].id == event_id
    assert capsys.readouterr().out.strip().splitlines()[-1] == event_id
