import pytest
from pydantic import ValidationError

from platform_api.settings import Settings


def test_owner_accounts_are_read_as_a_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_OWNER_ACCOUNTS", "id1, id2,")
    assert Settings().owner_accounts == ["id1", "id2"]
    assert Settings().session_ttl_days == 14


@pytest.mark.parametrize("days", [0, 15])
def test_a_session_length_outside_one_to_fourteen_days_is_refused(days: int) -> None:
    with pytest.raises(ValidationError):
        Settings(session_ttl_days=days)
