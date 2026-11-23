"""The Stripe reader: lists subscriptions, and nothing else.

Written for stripe-python 17.1.0 (uv.lock), whose pinned API version is `2026-11-18.endive`
(`stripe._api_version._ApiVersion.CURRENT`). At that version a subscription's period end is
on its items (`items.data[].current_period_end`), not on the subscription.

Read-only towards Stripe (CLAUDE.md rule 6): this file calls `subscriptions.list` and no
other Stripe method; a test reads the attribute names it uses. Pages are asked for by hand
with `starting_after`, so a test's stand-in for the service sees every call.

Any failure, a Stripe error or a subscription that cannot be built, becomes one
StripeReadError naming the exception's class only, raised without its cause: the text of a
Stripe or validation error can hold an address.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, Protocol, Self

import stripe

from platform_api.commerce.models import StripeSubscription
from platform_api.commerce.ports import StripeReadError
from platform_api.shared import clock

API_VERSION = "2026-11-18.endive"
_PAGE_SIZE = 100
_EXPAND = ["data.customer", "data.latest_invoice"]


class _SubscriptionList(Protocol):
    def list(self, params: Any = None, options: Any = None) -> Any: ...


class _EmptyPage(Exception):
    """A page said there is more but held no subscription."""


def page_from_json(data: dict[str, Any]) -> Any:
    """A recorded list response as the SDK's list object."""
    return stripe.convert_to_stripe_object(data)


def _time(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value), UTC)


def _expanded(value: Any) -> dict[str, Any] | None:
    """An expanded object as a dictionary; None when absent. An id alone is an error."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TypeError("an expected expansion is missing")
    return value


def _build(sub: dict[str, Any], provider_time: datetime) -> StripeSubscription:
    items = sub["items"]["data"]
    first = items[0] if items else None
    recurring = first["price"].get("recurring") if first is not None else None
    customer = _expanded(sub["customer"])
    email = None if customer is None or customer.get("deleted") else customer.get("email")
    application = sub["application"]
    if isinstance(application, dict):
        application = application["id"]
    past_due_since = None
    if sub["status"] == "past_due":
        invoice = _expanded(sub["latest_invoice"])
        past_due_since = _time(invoice["created"]) if invoice is not None else None
    return StripeSubscription(
        id=sub["id"],
        status=sub["status"],
        application=application,
        metadata=dict(sub["metadata"] or {}),
        customer_email=email,
        interval=recurring["interval"] if recurring is not None else None,
        start_date=_time(sub["start_date"]),
        current_period_end=_time(first["current_period_end"]) if first is not None else None,
        past_due_since=past_due_since,
        provider_time=provider_time,
    )


class StripeSdkReader:
    def __init__(self, api_key: str) -> None:
        client = stripe.StripeClient(api_key, stripe_version=API_VERSION)
        self._subscriptions: _SubscriptionList = client.v1.subscriptions

    @classmethod
    def for_test(cls, *, subscriptions: _SubscriptionList) -> Self:
        """A reader around a stand-in for `client.v1.subscriptions`."""
        reader = cls.__new__(cls)
        reader._subscriptions = subscriptions
        return reader

    def _page(self, after: str | None) -> tuple[list[StripeSubscription], bool]:
        params: dict[str, Any] = {"status": "all", "limit": _PAGE_SIZE, "expand": list(_EXPAND)}
        if after is not None:
            params["starting_after"] = after
        page = self._subscriptions.list(params=params)
        returned = clock.utcnow()
        built = [_build(s.to_dict(), returned) for s in page["data"]]
        more = bool(page["has_more"])
        if more and not built:
            raise _EmptyPage
        return built, more

    def subscriptions(self) -> Iterator[StripeSubscription]:
        after: str | None = None
        while True:
            try:
                built, more = self._page(after)
            except Exception as exc:
                raise StripeReadError(type(exc).__name__) from None
            yield from built
            if not more:
                return
            after = built[-1].id
