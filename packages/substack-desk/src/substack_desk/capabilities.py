"""What the desk may do, and through which door it reaches Substack."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict

Surface = Literal["official", "upload", "private"]


class Capability(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    surface: Surface
    enabled: bool
    note: str


class UnknownCapability(KeyError):
    pass


class CapabilityDisabled(RuntimeError):
    pass


_CAPABILITIES: dict[str, Capability] = {
    c.name: c
    for c in (
        Capability(
            name="subscriber_directory.file",
            surface="upload",
            enabled=True,
            note="The owner uploads Substack's export file",
        ),
        Capability(
            name="subscriber_directory.publisher_api",
            surface="official",
            enabled=False,
            note=(
                "Switched on when the publication has the Publisher API "
                "and the adapter exists"
            ),
        ),
    )
}

CAPABILITIES: Mapping[str, Capability] = MappingProxyType(_CAPABILITIES)


def require(name: str, capabilities: Mapping[str, Capability] = CAPABILITIES) -> Capability:
    capability = capabilities.get(name)
    if capability is None:
        known = ", ".join(sorted(capabilities))
        raise UnknownCapability(f"Unknown capability {name!r}. Known: {known}")
    if not capability.enabled:
        raise CapabilityDisabled(f"Capability {name} is switched off")
    return capability
