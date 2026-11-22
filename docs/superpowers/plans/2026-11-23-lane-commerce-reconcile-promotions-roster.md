# Lane L4 Commerce · Stripe Reconcile, Refresh, Promotions and Roster Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The platform learns who pays Substack. A job reads every subscription from Stripe, read-only, and hands what Stripe says to the entitlement engine; a member can ask for a fresh check; the upgrade page knows which routes and which promotion to show; and readers Stripe cannot see are imported from Substack's export file.

**Architecture:** `commerce` never decides access. It turns what a source says into `SourceState` records and calls `entitlements.public` (`plan_reconcile`, `apply_plan`). Stripe, the run records, the job starter and the roster inbox are **ports** (small interfaces with an in-memory version for tests); their cloud versions live in `commerce/adapters.py`. The Stripe key exists only in the job's environment: the API process starts the job and never reads Stripe.

**Tech Stack:** Python 3.12, Pydantic v2, the `stripe` SDK, `google-cloud-run` (to start a job), `google-cloud-storage`, `substack_desk` (the export reader), pytest. No new dependency except `substack-desk` as a path dependency.

**Spec:** [launch design](../specs/2026-11-19-launch-invites-grants-promotions-design.md) §5.3 and §5.5 · [contracts](../../contracts/stage-1-launch.md) §2, §3, §4, §5, §6, §8 · [03 commerce](../../architecture/03-commerce-and-revenue.md) §2, §3.1, §5a · [02](../../architecture/02-membership-and-entitlements.md) §4 (Rules 3 and 6, and the Stripe status table) · task cards M1 to M5.

**Lane rules:** change only `services/platform-api/src/platform_api/commerce/`, its tests under `services/platform-api/tests/commerce/`, and `services/platform-api/tests/recorded/stripe/`. Branch `commerce/reconcile` from `integration/stage-1`. Each task has a gate on the Core lane's plan, because it uses what that plan builds:

| Task | Starts when these Core tasks are merged | Because it uses |
| --- | --- | --- |
| 1, 2 | 1 to 5 | `SourceState`, `Guard`, `plan_reconcile`, `apply_plan`, `existing_for`, the `ent` fixture |
| 3 | 6 | `RateLimiter`, `member_with_terms`, the `idn` fixture and the fake identity provider |
| 4 | 6 and 8 | `access_for`, `launch_config`, `admin.public.owner`, `write_audit` |
| 5 | 5, and this plan's Task 0 | `upsert_contact`, `ChannelsPatch`; the `substack-desk` dependency |
| 6 | 8 and 9 | `AdminClient`, `cli.py`, the runtimes in `main.py` |

While you wait for a gate, do the next task whose gate is open. Changes outside your paths are the two `cross-lane` pull requests of Task 0 and Task 6.

### Task 0 (cross-lane, open it first): make `substack-desk` a dependency of the service

One pull request labelled `cross-lane`, reviewed by the Infra and Core lanes, with no other change in it: in `services/platform-api/pyproject.toml`, `substack-desk` in `dependencies` and `[tool.uv.sources] substack-desk = { path = "../../packages/substack-desk", editable = true }`; `uv.lock` regenerated; the image is built **from the repository root** (the `Dockerfile` copies `packages/substack-desk` and `services/platform-api`, and the workflow's `docker build` and its path filters include `packages/substack-desk/**`), because a path outside the build folder cannot be copied. Check: the existing `test` and `image` jobs pass, and `uv run python -c "import substack_desk"` works in `services/platform-api`.

## Global Constraints

- **Read-only towards Stripe.** The adapter calls list and retrieve methods only. No test and no code path calls a method that creates, updates, cancels or refunds. A test asserts this by listing the attribute names `commerce/stripe_adapter.py` uses.
- **Tests never call Stripe, Substack or Google.** Stripe responses are JSON files in `tests/recorded/stripe/`, written in the shape of Stripe's API for the SDK version in `uv.lock`, with invented ids (`sub_test_…`, `cus_test_…`) and addresses at `example.org`.
- **Never act on absence, never mass-expire, never grant on a guess** (02 §4, Rule 3). A failed or partial read of Stripe applies nothing.
- **No email address** in a log line, an event, a run record, a report or an exception message. `SourceState.email` is the only place an address travels. Every model that holds an address or a file's bytes sets `ConfigDict(hide_input_in_errors=True)`.
- **A run never stays `running`.** Every job function wraps its work so that any exception finishes the run as `failed` (the log line names the exception's class, never its message).
- **Alert markers are part of the log message text** (`logger.error("alert=reconcile_failed run=%s", run_id)`), not an `extra` field: the JSON formatter does not print extras.
- Source code imports from another module only what its `public.py` offers: from `entitlements.public`, the functions named in this plan and the models `SourceState`, `Guard`, `Entitlement`, `ChannelsPatch`, `Access`, `LaunchConfig`.
- `Runtime` gains each port's field in the task that creates the port's type, with a default of `None` or an in-memory version, so that `mypy` passes after every task.
- **No price, percentage, date of a promotion, or Stripe id of the real account** in the repository. Promotions are records written from the owner's private file.
- Settings of this lane are a class of its own, `commerce/settings.py: CommerceSettings(BaseSettings)` with prefix `PLATFORM_`, so that `settings.py` of the Core lane is not touched: `stripe_substack_application: str = ""`, `stripe_test_channel_metadata: bool = False` (refused when `env == "prod"`), `substack_grant_month` and `substack_grant_year` (each `Literal["tier:paid", "status:substack_paid"]`, default `status:substack_paid`), `reconcile_job: str = ""` (the job's full resource name), `roster_inbox_bucket: str = ""`, `grace_days: int = 21`.
- Time is passed in (`now`); jobs and routes take it from `shared.clock.utcnow()`.
- Check command for every task, in `services/platform-api`: `uv run ruff format tests && uv run pytest -m "not integration" && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run lint-imports`.

## Rulings by the integrator

1. **A dry run writes no contact and no entitlement.** It does write its own run record, marked `dry_run`, so the owner can read the counts afterwards.
2. **A roster row that has a plan interval is a card payer, and Stripe is the authority for card payers.** Such a row is never turned into an entitlement, whether or not Stripe shows a live subscription for the address; it is counted (`card_payer_rows`, and `card_payer_not_in_stripe` when Stripe shows none) so the owner can look. Only rows without a plan interval (complimentary, gift, billed by Apple) become roster records, and those are `status:substack_paid` (contracts 0.4).
3. **At launch the owner starts the two jobs with `gcloud run jobs execute`**, from the runbook, with `PLATFORM_JOB_DRY_RUN=1` for a dry run. `platform-cli runs show` prints the latest runs through one new admin route. The contracts page's `platform-cli stripe reconcile` and `platform-cli roster import` become runbook commands; this plan's pull request changes the page.
4. **A reader who already pays Substack on a plan that does not include the platform is offered `substack_change_plan` and no promotion.** Whether Substack's offer applies to a current payer is not known.

## Review Focus

1. **Stripe answers page 1 and fails on page 2.** Nothing is applied; the run is `failed`. Pinned in Task 2.
2. **A subscription with no customer address, or one created by someone other than Substack.** Skipped and counted, never guessed. Pinned in Task 1.
3. **Two members press "Check again" in the same second.** One job starts. Pinned in Task 3.
4. **An export older than a cancellation.** A card payer's row never becomes a roster record (ruling 2). Pinned in Task 5.
5. **A promotion after its end, or with the switch off.** Nothing is shown. Pinned in Task 4.

---

## File Structure

```
services/platform-api/
├─ src/platform_api/commerce/
│  ├─ settings.py        CommerceSettings
│  ├─ models.py          StripeSubscription, SyncRun, RefreshTicket, Promotion, PromotionView, Route, UpgradeOptions
│  ├─ ports.py           StripeReader, RunStore, PromotionStore, JobStarter, RosterInbox  (+ in-memory versions)
│  ├─ runtime.py         Runtime, set_runtime, get_runtime
│  ├─ mapping.py         classify, to_state                       (pure)
│  ├─ reconcile.py       stripe_reconcile
│  ├─ refresh.py         request_refresh
│  ├─ promotions.py      active_promotions, upgrade_options, count_upgrades
│  ├─ roster.py          roster_import
│  ├─ stripe_adapter.py  StripeSdkReader, page_from_json            (the only file that imports stripe)
│  ├─ adapters.py        FirestoreRunStore, FirestorePromotionStore, CloudRunJobStarter, BucketRosterInbox
│  ├─ public.py  http.py  jobs.py
└─ tests/
   ├─ commerce/test_mapping.py  test_reconcile.py  test_refresh.py  test_promotions.py  test_roster.py  test_adapters.py
   └─ recorded/stripe/subscriptions_page_1.json  subscriptions_page_2.json
```

---

### Task 1: From a Stripe subscription to a source state

**Files:**
- Create: `commerce/settings.py`, `models.py`, `mapping.py`; `tests/commerce/__init__.py`, `tests/commerce/test_mapping.py`

**Interfaces:**
- Consumes: `SourceState` from `entitlements.public`.
- Produces:

```python
class StripeSubscription(BaseModel):          # what the port returns: Stripe's object reduced to what the rules need
    id: str
    status: Literal["trialing", "active", "past_due", "incomplete", "incomplete_expired", "canceled", "unpaid", "paused"]
    application: str | None                   # the Connect application that created it
    metadata: dict[str, str]
    customer_email: str | None = Field(default=None, repr=False)
    interval: Literal["day", "week", "month", "year"] | None
    start_date: datetime
    current_period_end: datetime | None
    past_due_since: datetime | None           # when the unpaid invoice was created; set only while past_due
    provider_time: datetime                   # when the list call returned

Channel = Literal["substack", "platform"]
def classify(sub: StripeSubscription, settings: CommerceSettings) -> Channel | None: ...
Skip = Literal["not_substack", "no_address", "bad_address", "incomplete", "past_due_unknown"]
def to_state(sub: StripeSubscription, settings: CommerceSettings, now: datetime) -> SourceState | Skip: ...
```

- `classify`: `substack` when `application` equals `stripe_substack_application` (an empty setting matches nothing); also `substack` when `stripe_test_channel_metadata` is on and `metadata["test_channel"] == "substack"`. Everything else is `None` at launch (`platform` arrives with platform-only membership).
- `to_state` returns a `Skip` word for a subscription it cannot turn into a state (not Substack's; no address; an address `normalise_email` refuses; the cases marked below), and otherwise:

| Stripe status | State status | `valid_until` |
| --- | --- | --- |
| `trialing`, `active` (including one whose collection is paused) | `active` | `current_period_end` |
| `past_due`, and `now` is less than `grace_days` after `past_due_since` | `grace` | `past_due_since` + `grace_days` |
| `past_due`, `grace_days` or more after `past_due_since` | `expired` | `now` |
| `past_due` with `past_due_since` unknown | skipped as `past_due_unknown`: nothing ends on missing information | – |
| `canceled`, `unpaid`, `incomplete_expired`, `paused` (the status: a trial that ended without payment) | `expired` | `now` |
| `incomplete` | skipped as `incomplete` | – |

  `source = "substack_stripe"`, `source_ref = sub.id`, `started_at = start_date`, `plan_interval` is `month` or `year` (any other interval gives `None`), `grant` is `substack_grant_year` for `year` and `substack_grant_month` for everything else, `access_scope = "substack+platform"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/commerce/test_mapping.py
from datetime import timedelta

import pytest

from platform_api.commerce.mapping import classify, to_state
from platform_api.commerce.models import StripeSubscription
from platform_api.commerce.settings import CommerceSettings
from tests.fixtures.people import EMAIL, T0

S = CommerceSettings(stripe_substack_application="ca_test_substack", substack_grant_year="tier:paid")


def sub(name="ana", **over):
    base = dict(id=f"sub_test_{name}", status="active", application="ca_test_substack", metadata={},
                customer_email=EMAIL[name], interval="year", start_date=T0 - timedelta(days=200),
                current_period_end=T0 + timedelta(days=165), past_due_since=None, provider_time=T0)
    return StripeSubscription(**{**base, **over})


def test_an_annual_substack_subscription_becomes_a_paid_tier_state():
    state = to_state(sub(), S, T0)
    assert (state.source, state.source_ref, state.grant, state.status, state.plan_interval) == (
        "substack_stripe", "sub_test_ana", "tier:paid", "active", "year")
    assert (state.started_at, state.valid_until) == (T0 - timedelta(days=200), T0 + timedelta(days=165))


def test_a_monthly_plan_is_recorded_as_the_setting_says():
    assert to_state(sub("hal", interval="month"), S, T0).grant == "status:substack_paid"
    both = CommerceSettings(stripe_substack_application="ca_test_substack", substack_grant_month="tier:paid")
    assert to_state(sub("hal", interval="month"), both, T0).grant == "tier:paid"
    weekly = to_state(sub("hal", interval="week"), S, T0)
    assert (weekly.plan_interval, weekly.grant) == (None, "status:substack_paid")


@pytest.mark.parametrize(("status", "expected"), [("trialing", "active"), ("active", "active"), ("paused", "expired"),
                                                   ("canceled", "expired"), ("unpaid", "expired"), ("incomplete_expired", "expired")])
def test_statuses(status, expected):
    assert to_state(sub(status=status), S, T0).status == expected


def test_past_due_is_grace_for_twenty_one_days_then_expired():
    in_grace = to_state(sub(status="past_due", past_due_since=T0 - timedelta(days=20)), S, T0)
    assert (in_grace.status, in_grace.valid_until) == ("grace", T0 + timedelta(days=1))
    assert to_state(sub(status="past_due", past_due_since=T0 - timedelta(days=21)), S, T0).status == "expired"
    assert to_state(sub(status="past_due", past_due_since=None), S, T0) == "past_due_unknown"


def test_what_is_not_a_usable_substack_subscription_gives_no_state():
    assert to_state(sub(status="incomplete"), S, T0) == "incomplete"
    assert to_state(sub(customer_email=None), S, T0) == "no_address"
    assert to_state(sub(customer_email="not an address"), S, T0) == "bad_address"
    assert to_state(sub(application="ca_other"), S, T0) == "not_substack" and classify(sub(application=None), S) is None
    assert classify(sub(), CommerceSettings(stripe_substack_application="")) is None


def test_the_sandbox_marker_works_only_when_switched_on_and_never_in_prod():
    marked = sub(application=None, metadata={"test_channel": "substack"})
    assert classify(marked, S) is None
    assert classify(marked, CommerceSettings(stripe_test_channel_metadata=True)) == "substack"
    with pytest.raises(ValueError):
        CommerceSettings(env="prod", stripe_test_channel_metadata=True)


def test_a_subscription_never_prints_its_address():
    assert "@" not in repr(sub()) and "@" not in repr(to_state(sub(), S, T0))
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/commerce/test_mapping.py -v`
Expected: FAIL, `No module named 'platform_api.commerce.mapping'`.

- [ ] **Step 3: Implement**

`CommerceSettings` reads `PLATFORM_ENV` for the prod check (field `env`).

- [ ] **Step 4: See them pass**

Run the check command. Expected: 12 new tests pass (6 statuses, 6 others).

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "commerce: map a Stripe subscription to a source state; classify the channel"
```

---

### Task 2: The reconcile

**Files:**
- Create: `commerce/ports.py`, `runtime.py`, `reconcile.py`; `tests/commerce/conftest.py`, `tests/commerce/test_reconcile.py`
- Modify: `commerce/models.py`, `public.py`

**Interfaces:**
- Consumes: `entitlements.public.existing_for(sources) -> list[Entitlement]`, `plan_reconcile(existing, states, guard, now)`, `apply_plan(plan, run_id, now)`, `Guard`.
- Produces:

```python
# ports.py
class StripeReadError(Exception): ...
class StripeReader(Protocol):
    def subscriptions(self) -> Iterator[StripeSubscription]: ...      # every status, every page; raises StripeReadError
class RunStore(Protocol):
    def start(self, kind: RunKind, dry_run: bool, requested_by: RequestedBy, now: datetime) -> str: ...
    def finish(self, run_id: str, state: Literal["completed", "failed"], guard: Literal["passed", "blocked"] | None,
               counts: dict[str, int], now: datetime) -> None: ...
    def latest(self, kind: RunKind, *, completed_only: bool = False, real_only: bool = False) -> SyncRun | None: ...
    def acquire_start_slot(self, kind: RunKind, now: datetime, gap: timedelta) -> bool: ...   # atomic; Task 3
class InMemoryStripeReader: ...   # __init__(subs, fail_after: int | None = None): raises StripeReadError after that many items
class InMemoryRunStore: ...

# models.py
RunKind = Literal["stripe_reconcile", "roster_import"]
RequestedBy = Literal["schedule", "member", "owner"]
class SyncRun(BaseModel):
    run_id: str; kind: RunKind; dry_run: bool; state: Literal["running", "completed", "failed"]
    guard: Literal["passed", "blocked"] | None; requested_by: RequestedBy
    counts: dict[str, int]; started_at: datetime; finished_at: datetime | None

# runtime.py
@dataclass
class Runtime:
    settings: CommerceSettings; stripe: StripeReader | None; runs: RunStore; promotions: PromotionStore
    jobs: JobStarter | None; inbox: RosterInbox | None; limiter: RateLimiter; bus: EventBus

# public.py
def stripe_reconcile(dry_run: bool, requested_by: RequestedBy, now: datetime) -> SyncRun: ...
def last_reconcile_completed_at() -> datetime | None: ...
```

- `stripe_reconcile`, in order: start the run record; read **all** subscriptions into a list (a `StripeReadError` at any point → finish `failed` with what was counted so far, apply nothing, log one line at ERROR with the marker `alert=reconcile_failed`, return); map each with `to_state` and count `seen` and one count per `Skip` word; `plan_reconcile(existing_for(["substack_stripe"]), states, Guard(), now)`; when `dry_run`, apply nothing; otherwise `apply_plan`; finish `completed` with `guard` and the counts (`created`, `updated`, `ended`, `moved`, `unchanged`, `unseen`, `grants_created`, `tier_changes`, and for a dry run the numbers the plan would give); publish `commerce.reconcile.completed` (`run_id`, `kind`, `dry_run`, `guard`, counts); a blocked guard logs one line at ERROR with the marker `alert=reconcile_guard_blocked`. The owner's listing uses a further port method, `RunStore.recent(kind: RunKind | None, limit: int) -> list[SyncRun]`.
- `tests/commerce/conftest.py`: fixture `com` sets the runtime on top of the `ent` fixture: `CommerceSettings(stripe_substack_application="ca_test_substack", substack_grant_year="tier:paid", reconcile_job="projects/p/locations/l/jobs/stripe-reconcile")`, `bus=ent.bus`, in-memory versions of every port that exists so far, and `stripe=None` until a test sets it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/commerce/test_reconcile.py
import logging
from datetime import timedelta

from platform_api.commerce import public as commerce
from platform_api.commerce.ports import InMemoryStripeReader
from tests.commerce.test_mapping import sub
from tests.fixtures.people import T0

PEOPLE = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]


def test_a_real_run_creates_records_and_a_second_changes_nothing(com, ent):
    com.stripe = InMemoryStripeReader([sub("ana"), sub("hal", interval="month"), sub("bo", application="ca_other")])
    first = commerce.stripe_reconcile(False, "schedule", T0)
    second = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (first.state, first.guard, first.counts["created"], first.counts["not_substack"]) == ("completed", "passed", 2, 1)
    assert (second.counts["created"], second.counts["unchanged"]) == (0, 2)
    assert commerce.last_reconcile_completed_at() == T0 + timedelta(minutes=5)
    [event] = [e for e in ent.bus.published if e.type.endswith("commerce.reconcile.completed")][-1:]
    assert event.data["run_id"] == second.run_id and "@" not in event.model_dump_json()


def test_a_dry_run_writes_no_record_but_reports_what_it_would_do(com, ent):
    com.stripe = InMemoryStripeReader([sub("ana")])
    run = commerce.stripe_reconcile(True, "owner", T0)
    assert (run.dry_run, run.counts["created"]) == (True, 1)
    assert ent.store.entitlements_by_source("substack_stripe") == []
    assert commerce.last_reconcile_completed_at() is None            # a dry run is not a completed check


def test_a_read_that_fails_halfway_applies_nothing(com, ent, caplog):
    com.stripe = InMemoryStripeReader([sub(n) for n in PEOPLE])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE], fail_after=3)
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert run.state == "failed" and "reconcile_failed" in caplog.text
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_the_guard_blocks_a_mass_cancellation_and_alerts(com, ent, caplog):
    com.stripe = InMemoryStripeReader([sub(n) for n in PEOPLE])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub(n, status="canceled") for n in PEOPLE])
    with caplog.at_level(logging.ERROR):
        run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (run.state, run.guard, run.counts["ended"]) == ("completed", "blocked", 0)
    assert "reconcile_guard_blocked" in caplog.text
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_a_subscription_missing_from_the_list_is_left_alone(com, ent):
    com.stripe = InMemoryStripeReader([sub("ana"), sub("gus")])
    commerce.stripe_reconcile(False, "schedule", T0)
    com.stripe = InMemoryStripeReader([sub("ana")])
    run = commerce.stripe_reconcile(False, "schedule", T0 + timedelta(minutes=5))
    assert (run.counts["ended"], run.counts["unseen"]) == (0, 1)


def test_no_address_reaches_the_log_or_the_run_record(com, caplog):
    com.stripe = InMemoryStripeReader([sub("ana"), sub("ed", customer_email=None)])
    with caplog.at_level(logging.DEBUG):
        run = commerce.stripe_reconcile(False, "schedule", T0)
    assert "@" not in caplog.text and "@" not in run.model_dump_json() and run.counts["no_address"] == 1
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/commerce/test_reconcile.py -v`
Expected: FAIL, `No module named 'platform_api.commerce.ports'`.

- [ ] **Step 3: Implement**

`last_reconcile_completed_at` is `runs.latest("stripe_reconcile", completed_only=True, real_only=True)`'s `finished_at`, and only when its guard passed.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 6 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "commerce: stripe reconcile with dry run, run records, guard and failure handling"
```

---

### Task 3: "Check again"

**Files:**
- Create: `commerce/refresh.py`, `tests/commerce/test_refresh.py`
- Modify: `commerce/ports.py`, `models.py`, `public.py`, `http.py`

**Interfaces:**
- Produces: `JobStarter` (Protocol: `def start(self, job: str) -> None`; raises `JobStartError`) and `InMemoryJobStarter` (`started: list[str]`); `RefreshTicket(check: Literal["fresh", "started", "already_running"], last_completed_at: datetime | None, next_allowed_at: datetime)`; `class RateLimited(Exception)` with `retry_after: int`; `commerce.public.request_refresh(uid: str | None, now: datetime) -> RefreshTicket`; route `POST /v1/me/refresh-access` → 202 with the ticket (uses `member_with_terms` from `shared.http`; `RateLimited` → 429 `rate_limited`; `JobStartError` → 503 `unavailable`).
- `request_refresh`, in order: for a member (`uid` not `None`), the limits one a minute and six an hour through `Runtime.limiter` (keys `refresh:<uid>:m` and `refresh:<uid>:h`; the minute is checked first, so a request refused by the minute limit does not count toward the hour); the last real completed run finished less than 60 seconds ago → `fresh`; `runs.acquire_start_slot("stripe_reconcile", now, gap=60 seconds)` is false → `already_running`; otherwise `jobs.start(settings.reconcile_job)` → `started`. `next_allowed_at` is `now` + 60 seconds. With no job starter configured (`None`) the answer is `fresh` and nothing starts.

- [ ] **Step 1: Write the failing tests**

```python
# tests/commerce/test_refresh.py
from datetime import timedelta

import pytest

from platform_api.commerce import public as commerce
from platform_api.commerce.ports import InMemoryStripeReader
from platform_api.commerce.refresh import RateLimited
from tests.commerce.test_mapping import sub
from tests.fixtures.people import T0


def test_a_stale_check_starts_the_job_once(com):
    first = commerce.request_refresh("u-bo", T0)
    second = commerce.request_refresh("u-ed", T0 + timedelta(seconds=1))
    assert (first.check, second.check, com.jobs.started) == ("started", "already_running", [com.settings.reconcile_job])
    assert first.next_allowed_at == T0 + timedelta(seconds=60)


def test_a_run_completed_in_the_last_minute_is_reused(com):
    com.stripe = InMemoryStripeReader([sub("ana")])
    commerce.stripe_reconcile(False, "schedule", T0)
    ticket = commerce.request_refresh("u-bo", T0 + timedelta(seconds=30))
    assert (ticket.check, ticket.last_completed_at, com.jobs.started) == ("fresh", T0, [])
    assert commerce.request_refresh("u-ed", T0 + timedelta(seconds=90)).check == "started"


def test_one_member_is_limited_to_one_a_minute_and_six_an_hour(com):
    commerce.request_refresh("u-bo", T0)
    with pytest.raises(RateLimited) as err:
        commerce.request_refresh("u-bo", T0 + timedelta(seconds=20))
    assert 0 < err.value.retry_after <= 60
    for i in range(1, 6):
        commerce.request_refresh("u-bo", T0 + timedelta(minutes=2 * i))
    with pytest.raises(RateLimited):
        commerce.request_refresh("u-bo", T0 + timedelta(minutes=13))


def test_sign_in_is_not_limited_but_shares_the_start_slot(com):
    assert commerce.request_refresh(None, T0).check == "started"
    assert commerce.request_refresh(None, T0 + timedelta(seconds=5)).check == "already_running"


def test_without_a_job_starter_nothing_starts(com):
    com.jobs = None
    assert commerce.request_refresh("u-bo", T0).check == "fresh"


def test_the_route_answers_202_and_maps_the_limit(com, member_client):
    client, cookie = member_client("bo")
    first = client.post("/v1/me/refresh-access", headers=cookie)
    assert first.status_code == 202 and first.json()["check"] == "started"
    again = client.post("/v1/me/refresh-access", headers=cookie)
    assert again.status_code == 429 and again.json()["error"]["retry_after"] > 0
```

`member_client(name)` is a fixture in `tests/commerce/conftest.py`, on top of `com` and `idn`. It first makes sign-in possible: it reads the stored launch config and writes it back with `join_open=True`, `required_terms_version="t1"`, `required_privacy_version="p1"` and every other field unchanged, and stores a default campaign (`slug="members"`, `audience="public"`, no grant policy, `is_default=True`) if none exists. Then it signs the person in through `/v1/session/resolve` with the fake identity provider, accepts the terms, and returns the test client and the header.

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/commerce/test_refresh.py -v`
Expected: FAIL, `No module named 'platform_api.commerce.refresh'`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 6 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "commerce: refresh on request, one job at a time, limited per member"
```

---

### Task 4: Promotions and upgrade options

**Files:**
- Create: `commerce/promotions.py`, `tests/commerce/test_promotions.py`
- Modify: `commerce/ports.py`, `models.py`, `public.py`, `http.py`, `reconcile.py`

**Interfaces:**
- Consumes: `entitlements.public.access_for`, `launch_config`; `admin.public.owner`.
- Produces:

```python
Audience = Literal["guests", "free_members", "paid_members"]
class Promotion(BaseModel):                     # the stored record; contracts §4
    id: str; channel: Literal["substack_offer", "platform_checkout"]; audience: list[Audience]
    plan_interval: Literal["month", "year"] | None; starts_at: datetime; ends_at: datetime
    substack_offer_url: str | None; display: dict[str, str]; counts: dict[str, int]
class PromotionView(BaseModel): ...             # contracts §2: id, channel, plan_interval, starts_at, ends_at, url, display
class Route(BaseModel): kind: Literal["substack", "platform_only", "substack_change_plan"]; available: bool; url: str | None
class UpgradeOptions(BaseModel): routes: list[Route]; promotion: PromotionView | None

def active_promotions(audience: Audience, now: datetime) -> list[PromotionView]: ...
def upgrade_options(uid: str, now: datetime) -> UpgradeOptions: ...
def put_promotions(promotions: list[Promotion], actor: str) -> int: ...
def count_upgrades(created: Sequence[Entitlement], existing: Sequence[Entitlement], now: datetime) -> int: ...
```

- `PromotionStore` port: `list()`, `put_all(promotions)` (keeps the counts of an id that exists), `count_once(promotion_id, contact_id) -> bool` (atomic: the first time only, it adds one to `counts["upgrades_in_window"]` and returns true).
- `active_promotions`: empty while `promotions_open` is off; otherwise the promotions with `starts_at <= now < ends_at` whose `audience` contains the one asked for; `substack_offer` without a URL is never shown.
- `upgrade_options`: tier `paid` → no routes, no promotion. A member with a live reason labelled `substack_status` → one route `substack_change_plan` (`url` = `substack_account_url`; `available` false when that is empty) and no promotion (ruling 4). Anyone else → `substack` (`url` = the active promotion's URL when there is one for `free_members`, else `substack_account_url`; `available` is false and `url` is `null` when neither exists) and `platform_only` with `available: false`; `promotion` = the first active one for `free_members`.
- `count_upgrades`, called by `stripe_reconcile` after a real apply with the plan's created `substack_stripe` records: for each promotion (open or ended), a created record whose `valid_from` is inside the window, for a contact that had no `substack_stripe` or `substack_roster` record live at `starts_at` among `existing`, is counted once per promotion and contact (`count_once`): `counts["upgrades_in_window"]` + 1 and the event `commerce.promotion.upgrade_counted` (`promotion_id`, `contact_id`, `channel`, `source_ref`).
- Routes: `GET /v1/public/promotions/active` (audience `guests`; header `Cache-Control: public, max-age=60`), `GET /v1/me/upgrade-options` (`member_with_terms`), `PUT /v1/admin/promotions` `{promotions: [...]}` (dependency `owner`; validation: unique ids, `starts_at < ends_at`, a URL that starts with `https://` for `substack_offer`; → `{written}`), and `GET /v1/admin/promotions` → `{promotions: [{id, channel, starts_at, ends_at, counts}]}`. Both write an audit entry through `entitlements.public.write_audit` (subject `admin`, actions `promotions.written` and `admin.read`): every owner call is audited, reads included.

- [ ] **Step 1: Write the failing tests**

```python
# tests/commerce/test_promotions.py
from datetime import timedelta

import pytest

from platform_api.commerce import public as commerce
from platform_api.commerce.models import Promotion
from platform_api.commerce.ports import InMemoryStripeReader
from platform_api.entitlements.models import LaunchConfig
from tests.commerce.test_mapping import sub
from tests.fixtures.people import T0

START, END = T0 + timedelta(days=6), T0 + timedelta(days=11)


def promo(**over):
    base = dict(id="offer-1", channel="substack_offer", audience=["free_members", "guests"], plan_interval="year",
                starts_at=START, ends_at=END, substack_offer_url="https://example.org/offer", display={"badge": "b", "headline": "h", "body": "x"}, counts={})
    return Promotion(**{**base, **over})


@pytest.fixture
def open_shop(com, ent):
    ent.store.put_launch_config(LaunchConfig(join_open=True, promotions_open=True, substack_account_url="https://example.org/subscribe"))
    commerce.put_promotions([promo()], "owner:acc-1")
    return com


@pytest.mark.parametrize(("when", "shown"), [(START - timedelta(seconds=1), 0), (START, 1), (END - timedelta(seconds=1), 1), (END, 0)])
def test_a_promotion_shows_only_inside_its_window(open_shop, when, shown):
    assert len(commerce.active_promotions("guests", when)) == shown


def test_the_switch_hides_everything_and_the_audience_filters(open_shop, ent):
    assert commerce.active_promotions("paid_members", START) == []
    ent.store.put_launch_config(LaunchConfig(join_open=True, promotions_open=False))
    assert commerce.active_promotions("guests", START) == []


def test_the_view_carries_no_counts_and_the_offer_link(open_shop):
    [view] = commerce.active_promotions("guests", START)
    assert view.url == "https://example.org/offer" and "counts" not in view.model_dump()


def test_upgrade_options_by_kind_of_member(open_shop, signed_in):
    free = commerce.upgrade_options(signed_in("bo"), START)
    assert [(r.kind, r.available, r.url) for r in free.routes] == [("substack", True, "https://example.org/offer"), ("platform_only", False, None)]
    assert free.promotion.id == "offer-1"
    assert commerce.upgrade_options(signed_in("bo"), END).routes[0].url == "https://example.org/subscribe"
    monthly = commerce.upgrade_options(signed_in("hal"), START)
    assert [(r.kind, r.url) for r in monthly.routes] == [("substack_change_plan", "https://example.org/subscribe")] and monthly.promotion is None
    paid = commerce.upgrade_options(signed_in("ana"), START)
    assert (paid.routes, paid.promotion) == ([], None)


def test_cy_is_counted_once_and_a_reader_who_already_paid_is_not(open_shop, ent):
    open_shop.stripe = InMemoryStripeReader([sub("ana")])
    commerce.stripe_reconcile(False, "schedule", T0)
    inside = START + timedelta(days=1)
    open_shop.stripe = InMemoryStripeReader([sub("ana"), sub("cy", start_date=inside), sub("ana", id="sub_test_ana_2", start_date=inside)])
    commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=1))
    commerce.stripe_reconcile(False, "schedule", inside + timedelta(hours=2))
    [stored] = open_shop.promotions.list()
    counted = [e for e in ent.bus.published if e.type.endswith("commerce.promotion.upgrade_counted")]
    assert stored.counts == {"upgrades_in_window": 1} and len(counted) == 1 and "@" not in counted[0].model_dump_json()


def test_the_owner_route_validates(open_shop, owner_client):
    good = promo(id="offer-2").model_dump(mode="json")
    assert owner_client.put("/v1/admin/promotions", json={"promotions": [good]}).json() == {"written": 1}
    for bad in ({**good, "ends_at": good["starts_at"]}, {**good, "substack_offer_url": "http://example.org/x"}):
        assert owner_client.put("/v1/admin/promotions", json={"promotions": [bad]}).status_code == 422
    assert owner_client.put("/v1/admin/promotions", json={"promotions": [good, good]}).status_code == 422


def test_the_public_route_is_cacheable_for_a_minute(open_shop, owner_client):
    r = owner_client.get("/v1/public/promotions/active", headers={"Authorization": ""})
    assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=60" and "promotions" in r.json()
```

`signed_in(name)` (runs one reconcile at `T0` with `sub("ana")` and `sub("hal", interval="month")` the first time it is called, then signs the person in the way `member_client` does, which keeps `promotions_open` and `substack_account_url` as `open_shop` set them, and returns the uid) and `owner_client` (a test client whose `Authorization` header passes the `owner` dependency) are fixtures in `tests/commerce/conftest.py`, built from the Core lane's test helpers. Route handlers use the frozen clock (`T0`), which is outside the promotion's window, so the public route answers an empty list here.

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/commerce/test_promotions.py -v`
Expected: FAIL, `No module named 'platform_api.commerce.promotions'`.

- [ ] **Step 3: Implement, and call `count_upgrades` from `stripe_reconcile`**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 10 new tests pass (4 windows, 6 others).

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "commerce: promotions in their window, upgrade options per member, upgrades counted once"
```

---

### Task 5: Readers Stripe cannot see

**Files:**
- Create: `commerce/roster.py`, `tests/commerce/test_roster.py`
- Modify: `commerce/ports.py`, `public.py`

**Interfaces:**
- Consumes: `substack_desk.adapters.export_file.FileDirectory`, `ExportHeaderError`; `entitlements.public.existing_for`, `contact_id_for`, `upsert_contact`, `plan_reconcile`, `apply_plan`.
- Produces: `RosterInbox` (Protocol: `def newest(self) -> RosterObject | None`, with `RosterObject(name: str, data: bytes = Field(repr=False), updated_at: datetime)`) and `InMemoryRosterInbox`; `commerce.public.roster_import(dry_run: bool, now: datetime) -> SyncRun`.
- `roster_import`, in order:
  1. Refuse (run `failed`, count `refused_no_recent_reconcile: 1`, ERROR line with the marker `alert=roster_refused`) unless the latest real `stripe_reconcile` run is `completed`, its guard `passed`, and it finished less than 24 hours ago.
  2. No object in the inbox → `failed`, `no_file: 1`.
  3. `FileDirectory(object.data, object.updated_at).list_paid()`. `ExportHeaderError` → `failed`, `bad_header: 1`, and the ERROR line names the missing columns. `complete` false → `failed`, `truncated: 1`, the marker `alert=roster_truncated`, nothing applied.
  4. For every record: `upsert_contact(email, ChannelsPatch(substack={"type": record.type, "plan_interval": record.plan_interval, "last_seen_in_roster": now.isoformat()}))` (not in a dry run). A record with a plan interval → count `card_payer_rows`, and `card_payer_not_in_stripe` when its contact has no live `substack_stripe` record; no state (ruling 2). A record without one → a state: `source="substack_roster"`, `source_ref="roster"`, `grant="status:substack_paid"`, `status="active"`, `started_at` = `record.since`, else the `valid_from` of the roster record this person already has, else `listing.exported_at` (so a second upload of a file without dates changes nothing), `valid_until = record.paid_until`, `plan_interval=None`.
  5. `plan_reconcile(existing_for(["substack_roster"]), states, Guard(), now)`; apply unless dry run. No state is ever `expired`, so the import ends nothing; records the file does not mention are `unseen`.
  6. Finish with the plan's counts plus `rows`, `rejected_rows` and the Desk report's `free_rows` and `trial_rows`. The Desk report's `unknown_types` and `unknown_plans` are logged at WARNING (values, not addresses).

- [ ] **Step 1: Write the failing tests**

```python
# tests/commerce/test_roster.py
import logging
from datetime import timedelta

from platform_api.commerce import public as commerce
from platform_api.commerce.ports import InMemoryRosterInbox, InMemoryStripeReader, RosterObject
from platform_api.entitlements import public as ent_api
from tests.commerce.test_mapping import sub
from tests.fixtures.people import EMAIL, T0

HEADER = "Email,Type,Stripe plan,First paid date,Expiration date"


def export(*rows):
    return ("\r\n".join([HEADER, *rows]) + "\r\n").encode()


def ready(com, *rows, reconcile_at=T0):
    com.stripe = InMemoryStripeReader([sub("gus"), sub("ana")])
    commerce.stripe_reconcile(False, "schedule", reconcile_at)
    com.inbox = InMemoryRosterInbox(RosterObject(name="export.csv", data=export(*rows), updated_at=T0))


DI = f"{EMAIL['di']},Comp,,,"
GUS = f"{EMAIL['gus']},Paid,$5 a year,2026-01-01T00:00:00.000Z,"
ED = f"{EMAIL['ed']},Paid,$5 a year,2026-01-01T00:00:00.000Z,"
BO = f"{EMAIL['bo']},Free,,,"


def test_di_is_recognised_as_a_status_and_gus_gets_nothing_from_the_roster(com, ent):
    ready(com, DI, GUS, BO)
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    roster = ent.store.entitlements_by_source("substack_roster")
    assert [(e.contact_id, e.grant, e.plan_interval) for e in roster] == [(ent_api.contact_id_for(EMAIL["di"]), "status:substack_paid", None)]
    assert (run.state, run.counts["created"], run.counts["card_payer_rows"], run.counts["card_payer_not_in_stripe"]) == ("completed", 1, 1, 0)
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])).channels["substack"]["type"] == "comp"


def test_a_card_payer_stripe_does_not_show_is_reported_not_granted(com, ent):
    ready(com, ED)
    run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert ent.store.entitlements_by_source("substack_roster") == [] and run.counts["card_payer_not_in_stripe"] == 1


def test_importing_twice_and_importing_a_shorter_file_end_nothing(com, ent):
    ready(com, DI)
    commerce.roster_import(False, T0 + timedelta(hours=1))
    com.inbox = InMemoryRosterInbox(RosterObject(name="e2.csv", data=export(BO), updated_at=T0 + timedelta(hours=2)))
    run = commerce.roster_import(False, T0 + timedelta(hours=3))
    assert (run.counts["ended"], run.counts["unseen"]) == (0, 1)
    assert [e.status for e in ent.store.entitlements_by_source("substack_roster")] == ["active"]


def test_a_dry_run_writes_nothing(com, ent):
    ready(com, DI)
    run = commerce.roster_import(True, T0 + timedelta(hours=1))
    assert run.counts["created"] == 1 and ent.store.entitlements_by_source("substack_roster") == []
    assert ent.store.get_contact(ent_api.contact_id_for(EMAIL["di"])) is None


def test_a_cut_off_file_applies_nothing_and_alerts(com, ent, caplog):
    ready(com, DI)
    com.inbox = InMemoryRosterInbox(RosterObject(name="cut.csv", data=export(DI)[:-8], updated_at=T0))
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert (run.state, run.counts["truncated"]) == ("failed", 1) and "roster_truncated" in caplog.text
    assert ent.store.entitlements_by_source("substack_roster") == [] and "@" not in caplog.text


def test_the_import_refuses_without_a_recent_good_reconcile(com, ent, caplog):
    com.inbox = InMemoryRosterInbox(RosterObject(name="e.csv", data=export(DI), updated_at=T0))
    with caplog.at_level(logging.ERROR):
        never = commerce.roster_import(False, T0)
    ready(com, DI, reconcile_at=T0)
    stale = commerce.roster_import(False, T0 + timedelta(hours=25))
    assert (never.state, stale.state) == ("failed", "failed") and stale.counts["refused_no_recent_reconcile"] == 1
    assert "roster_refused" in caplog.text and ent.store.entitlements_by_source("substack_roster") == []


def test_a_missing_column_fails_and_names_it(com, caplog):
    ready(com, DI)
    com.inbox = InMemoryRosterInbox(RosterObject(name="e.csv", data=b"Email,Stripe plan\r\nx@example.org,\r\n", updated_at=T0))
    with caplog.at_level(logging.ERROR):
        run = commerce.roster_import(False, T0 + timedelta(hours=1))
    assert run.counts["bad_header"] == 1 and "Type" in caplog.text and "@" not in caplog.text
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/commerce/test_roster.py -v`
Expected: FAIL, `No module named 'platform_api.commerce.roster'` (Task 0 must be merged, or `substack_desk` cannot be imported).

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 7 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "commerce: roster import for readers Stripe cannot see; refuses without a good reconcile"
```

---

### Task 6: Cloud versions of the ports, the jobs, and the wiring

**Files:**
- Create: `commerce/stripe_adapter.py`, `commerce/adapters.py`, `tests/commerce/test_adapters.py`, `tests/recorded/stripe/subscriptions_page_1.json`, `subscriptions_page_2.json`
- Modify: `commerce/jobs.py`, `commerce/http.py`
- Cross-lane pull request (label `cross-lane`, reviewed by the Core lane): `main.py` (build the `commerce` runtime lazily; set `identity`'s `request_refresh` to a function that calls `commerce.request_refresh(None, now)`, answers `"fresh"` for `fresh` and `"started"` otherwise, and answers `"fresh"` when a `JobStartError` is raised, so that a job that cannot start never fails a sign-in; set `last_reconcile_at` to `commerce.last_reconcile_completed_at`), `admin/client.py` (methods `sync_runs`, `promotions_put`, `promotions_list`), `cli.py` (commands `runs show [--kind]` and `promo apply --file`; `launch report` also prints each promotion's counts).

**Interfaces:**
- `stripe_adapter.py`: `StripeSdkReader(api_key: str)`: one `stripe.StripeClient`; `subscriptions()` calls `client.v1.subscriptions.list` with `status="all"`, `limit=100`, expanding the customer and the latest invoice, and **pages by hand**: while the page says `has_more`, it asks again with `starting_after` = the last id (the SDK's automatic paging would bypass the stand-in used in tests). It builds `StripeSubscription` (`interval` from the first item's price; `current_period_end` from the first subscription item, where the pinned API version keeps it; `past_due_since` = the latest invoice's creation time when the status is `past_due`). Any `stripe.StripeError`, and any error while building a `StripeSubscription` (an unknown status, a missing field), becomes `StripeReadError` whose message is the exception's class name only. Read items with `sub["items"]`: attribute access returns the dictionary's own method. **Before writing it, read Stripe's API reference for the SDK version in `uv.lock`** and write the two recorded pages in exactly that shape, page 1 with `"has_more": true`; state the API version in a comment at the top of the adapter. The recorded pages hold four subscriptions: first one made by Substack's application, then one by another application, one with a deleted customer (no address), and one `past_due` with a latest invoice.
- `FirestoreRunStore`, `FirestorePromotionStore` (collections `sync_runs`, `promotions`, `promotion_upgrades`, and the document `config/reconcile_slot` for `acquire_start_slot`, written in a transaction), `CloudRunJobStarter(client)` (`JobsClient.run_job(name=<job>)`; it does not wait for the job), `BucketRosterInbox(client, bucket)` (the most recently updated object).
- `commerce/jobs.py`: `JOBS = {"stripe-reconcile": …, "roster-import": …}`. Each builds the runtime it needs, reads `PLATFORM_JOB_DRY_RUN` (`1` → dry run) and `PLATFORM_JOB_REQUESTED_BY` (default `schedule`) from the environment, runs, prints the run as one JSON line, and returns `0` for `completed` with guard `passed`, `1` for `failed`, `2` for a blocked guard. `stripe-reconcile` reads the name of the secret from `PLATFORM_STRIPE_KEY_SECRET` (contracts §6) and fetches the key from Secret Manager at start (`adapters.read_secret(name) -> str`, never logged); the API service's identity cannot read that secret, and `request_refresh` never builds a `StripeSdkReader`.
- `GET /v1/admin/sync-runs?kind=&limit=` (dependency `owner`; `limit` at most 20; audited as `admin.read`) → `{runs: [SyncRun]}`, from `RunStore.recent`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/commerce/test_adapters.py
import ast
import json
from pathlib import Path

import pytest

from platform_api.commerce import stripe_adapter as adapters
from platform_api.commerce.mapping import to_state
from platform_api.commerce.ports import StripeReadError
from platform_api.commerce.settings import CommerceSettings
from tests.fixtures.people import T0

RECORDED = Path(__file__).parents[1] / "recorded" / "stripe"


class FakeSubscriptions:
    def __init__(self, pages, fail_on=None):
        self.pages, self.fail_on, self.calls = pages, fail_on, []

    def list(self, params=None, options=None):
        self.calls.append(params)
        index = len(self.calls) - 1
        if self.fail_on == index:
            import stripe
            raise stripe.APIConnectionError("could not reach api.stripe.com for cus_test_1")
        return adapters.page_from_json(self.pages[index])


def reader(pages, fail_on=None):
    fake = FakeSubscriptions(pages, fail_on)
    return adapters.StripeSdkReader.for_test(subscriptions=fake), fake


def pages():
    return [json.loads((RECORDED / f"subscriptions_page_{n}.json").read_text()) for n in (1, 2)]


def test_both_recorded_pages_are_read_and_mapped():
    r, fake = reader(pages())
    subs = list(r.subscriptions())
    assert len(subs) == 4 and len(fake.calls) == 2 and fake.calls[0]["status"] == "all"
    settings = CommerceSettings(stripe_substack_application=subs[0].application, substack_grant_year="tier:paid")
    states = [to_state(s, settings, T0) for s in subs]
    assert sum(s is not None for s in states) >= 1 and any(s.customer_email is None for s in subs)
    assert any(s.status == "past_due" and s.past_due_since is not None for s in subs)


def test_a_failure_on_the_second_page_is_one_error_without_details():
    r, _ = reader(pages(), fail_on=1)
    with pytest.raises(StripeReadError) as err:
        list(r.subscriptions())
    assert str(err.value) == "APIConnectionError"


def test_the_stripe_adapter_only_reads():
    tree = ast.parse(Path(adapters.__file__).read_text())
    called = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not called & {"create", "modify", "update", "delete", "cancel", "refund", "pause", "resume"}   # so no dict.update() in this file either


def test_the_recorded_pages_hold_only_invented_people():
    text = "".join((RECORDED / f"subscriptions_page_{n}.json").read_text() for n in (1, 2))
    assert "@" not in text.replace("@example.org", "") and "sub_test_" in text and '"livemode": false' in text


def test_the_jobs_are_registered():
    from platform_api.cli import build_registry
    assert {"stripe-reconcile", "roster-import", "selfcheck"} <= set(build_registry())
```

`page_from_json` and `StripeSdkReader.for_test` are small seams in `stripe_adapter.py`: the first turns recorded JSON into the SDK's list object, the second builds a reader around a stand-in for `client.subscriptions`.

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/commerce/test_adapters.py -v`
Expected: FAIL, `No module named 'platform_api.commerce.stripe_adapter'`.

- [ ] **Step 3: Implement; open the cross-lane pull request**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 5 new tests pass; `tests/test_module_registration.py` still passes (no duplicate job name).

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "commerce: Stripe, Firestore, Cloud Run and bucket adapters; the two jobs; run listing for the owner"
```

---

## Exit test for this plan

1. The check command passes in CI on the branch and on the cross-lane branch.
2. The hand-over lists for the Infra lane: the two jobs and their environment variables; that only `stripe-reconcile` gets the Stripe key; the permission the API service needs to start that one job; the settings `PLATFORM_STRIPE_KEY_SECRET` (on the reconcile job only), `PLATFORM_STRIPE_SUBSTACK_APPLICATION`, `PLATFORM_SUBSTACK_GRANT_MONTH`, `PLATFORM_SUBSTACK_GRANT_YEAR`, `PLATFORM_RECONCILE_JOB`, `PLATFORM_ROSTER_INBOX_BUCKET`; the Firestore indexes on `sync_runs` (`kind`, `finished_at`; and `kind`, `state`, `dry_run`, `finished_at`); and the four log markers to alert on (`reconcile_failed`, `reconcile_guard_blocked`, `roster_refused`, `roster_truncated`).
3. The hand-over lists for the owner what to check at Gate 2 against the sandbox: that a recorded page matches a real list response, whether the account leaves an unpaid subscription `past_due` across several invoices (the 21 days are counted from the latest unpaid invoice), and how Substack's application id is read from one real subscription (a read-only call; the id goes into Terraform variables, not into this repository).
