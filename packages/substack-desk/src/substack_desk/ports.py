"""The port the platform depends on; adapters implement it."""

from typing import Protocol

from substack_desk.models import DirectoryListing


class SubscriberDirectory(Protocol):
    def list_paid(self) -> DirectoryListing: ...
