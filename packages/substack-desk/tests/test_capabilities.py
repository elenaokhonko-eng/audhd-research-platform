import pytest

from substack_desk.capabilities import (
    CAPABILITIES,
    Capability,
    CapabilityDisabled,
    UnknownCapability,
    require,
)


def test_the_file_directory_is_available():
    assert require("subscriber_directory.file").surface == "upload"


def test_the_publisher_api_is_listed_but_switched_off():
    assert CAPABILITIES["subscriber_directory.publisher_api"].enabled is False
    with pytest.raises(CapabilityDisabled, match="subscriber_directory.publisher_api"):
        require("subscriber_directory.publisher_api")


def test_an_unknown_name_lists_the_known_ones():
    with pytest.raises(UnknownCapability) as err:
        require("notes.publish")
    assert "subscriber_directory.file, subscriber_directory.publisher_api" in str(err.value)


def test_nothing_that_uses_a_private_surface_is_on_by_default():
    assert [c.name for c in CAPABILITIES.values() if c.surface == "private" and c.enabled] == []


def test_the_matrix_cannot_be_changed_at_run_time():
    with pytest.raises(TypeError):
        CAPABILITIES["x"] = Capability(name="x", surface="private", enabled=True, note="")  # type: ignore[index]


def test_require_reads_the_matrix_it_is_given():
    custom = {"a.b": Capability(name="a.b", surface="official", enabled=True, note="")}
    assert require("a.b", custom).name == "a.b"
