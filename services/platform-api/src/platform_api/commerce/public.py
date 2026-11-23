from datetime import datetime

from platform_api.commerce.reconcile import stripe_reconcile
from platform_api.commerce.runtime import get_runtime

__all__ = ["last_reconcile_completed_at", "stripe_reconcile"]


def last_reconcile_completed_at() -> datetime | None:
    """When the last real reconcile finished with its guard passed; a dry run does not count."""
    run = get_runtime().runs.latest("stripe_reconcile", completed_only=True, real_only=True)
    if run is None or run.guard != "passed":
        return None
    return run.finished_at
