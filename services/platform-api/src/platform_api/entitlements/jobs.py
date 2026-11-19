from collections.abc import Callable

from platform_api.settings import Settings

JOBS: dict[str, Callable[[Settings], int]] = {}
