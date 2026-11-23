# Lane L1 Core · Entitlements, Campaigns and Sign-in Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `platform-api` can say who a person is and what they may open: it turns a verified sign-in into a member, claims the entitlements that wait for them, applies what a payment source says, creates the launch grant when a campaign's policy is met, and serves the member and owner routes of the contracts page.

**Architecture:** The rules are pure functions over lists of records, tested without any cloud. Everything that touches the outside (Firestore, Cloud KMS, Identity Platform) sits behind a **port**: a small interface with an in-memory version for tests and a cloud version wired in `main.py`. Each feature module keeps its ports in one `Runtime` object that tests replace. Tasks 1 to 5 build the entitlement engine; tasks 6 to 8 build sign-in and the routes; task 9 adds the cloud versions of the ports.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, `firebase-admin` (Identity Platform), `google-cloud-kms`, `google-cloud-firestore`, pytest. All are already in `pyproject.toml`.

**Spec:** [launch design](../specs/2026-11-19-launch-invites-grants-promotions-design.md) §5.2 to §5.4 · [contracts](../../contracts/stage-1-launch.md) §1 to §6 and §8 (version 0.4) · [02 membership and entitlements](../../architecture/02-membership-and-entitlements.md) §3 and §4 · [09 data model](../../architecture/09-events-and-data-model.md) §2 · task cards C2 to C7 of the [swarm build plan](../../plans/stage-1-swarm-build-plan.md).

**Lane rules:** change only the Core lane's paths under `services/platform-api/` (not `commerce/`, `library/`, `content/`). Branch `core/entitlements-and-sign-in` from `integration/stage-1`. One draft pull request against it, opened after Task 1 and kept up to date. **Push after every task, and after Tasks 1, 3 and 5 mark the pull request ready and ask the integrator to merge what exists**, then continue on a new branch from `integration/stage-1`: the Commerce and Library lanes wait for the interfaces of Tasks 1 to 5.

## Global Constraints

- Names, signatures and shapes are those of the contracts page. Where this plan adds a name the contracts page does not have, it says so; anything else that seems missing is a question for the integrator, not something to invent.
- **No email address** in a log line, an event, an exception message, a `repr`, an audit entry's text, or a response body. A model field that holds an address is declared `Field(repr=False)`. The address is stored in exactly two documents: `contacts/{contact_id}.email` and `members/{uid}.email`.
- Entitlements **fail safe** (02 §4, Rule 3): nothing is ended on missing information, nothing is granted without a verified fact, and a run that would end too many records ends none.
- Every function of a module's `public.py` is the only way another module or the HTTP layer uses that module. `uv run lint-imports` must pass.
- Time is always passed in (`now: datetime`, timezone-aware, UTC). No rule reads the clock itself; route handlers and jobs call `shared.clock.utcnow()` and pass the value down.
- Ids: `contact_id` is the first 32 hex characters of HMAC-SHA256 over the trimmed, lower-cased address, computed by the contact key. `entitlement_id = sha256(f"{source}:{source_ref}:{contact_id}:{grant}")[:32]`. A launch grant has `source = "grant"` and `source_ref = "campaign:<slug>"`.
- Test people are the eight of contracts §8, in `tests/fixtures/people.py`, at `example.org`. Tests never call Google, Stripe or Substack.
- Models that hold an address also set `model_config = ConfigDict(hide_input_in_errors=True)`: `repr=False` does not hide the value inside a validation error.
- Three functions stamp a record with the time and take no `now`: `upsert_contact`, `claim_for_member` and `record_arrival` call `shared.clock.utcnow()`. They decide nothing from it.
- Test code in this plan is not formatted to the project's style. After writing a test file, run `uv run ruff format tests` before the check command.
- `tests/conftest.py` imports a feature module **inside** the fixture that needs it, never at the top, so that the suite still collects before that module exists.
- Check command for every task, in `services/platform-api`: `uv run pytest -m "not integration" && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run lint-imports`.

## Rulings by the integrator (they refine the contracts page; the pull request that carries this plan records them there)

1. **`plan_reconcile` derives contact ids through the key port, then calls a pure function.** The pure part is `entitlements.reconcile.plan(existing, resolved, guard)`, and that is what the rule tests exercise.
2. **`record_arrival` does not write the member document** (the member belongs to `identity`). `identity` stores `joined_via` itself when it creates the member, and calls `record_arrival` on that first sign-in only. `record_arrival` updates the contact's `invite`, the campaign's counts, and publishes `membership.campaign.joined`.
3. **`apply_plan` compares the tier before the plan with the tier after the plan and after the grant policies**, and publishes at most one `membership.tier.changed` per member. A reader recognised and granted in the same run gets one event, not two.
4. **A reader with no plan interval** (`di`, complimentary) is recorded as `status:substack_paid` and gets no launch grant from a policy that names plan intervals (contracts 0.4). The task card's phrase "`di` gets one through the roster" is replaced by: `di` is recognised, has the free workspace, and becomes paid through an owner grant.
5. **When `join_open` is off**, a person with no member document cannot sign in (403 `forbidden`); an existing member can.
6. **`identity` asks for a refresh through a port** (`Runtime.request_refresh`), which is `None` until the Commerce lane's `request_refresh` exists. With `None`, `join.check` is `"fresh"`.

## Review Focus

1. **The same person under two spellings of one address** (`Ana@Example.org `, `ana@example.org`) must be one contact. Pinned in Task 1.
2. **A source that says nothing about a record** must not end it; **a source that fails halfway** must not end the rest. Pinned in Task 4 (`unseen`, the guard).
3. **A grant evaluated twice, or by two requests at once**, must exist once. Pinned in Task 5 (deterministic id) and Task 9 (create-if-absent in a transaction).
4. **A cookie that was revoked, belongs to a deleted member, or is garbage** must be refused on every route. Pinned in Task 6.
5. **An address reaching a log line** through an exception or a `repr`. Pinned in Tasks 1, 6 and 8 by tests that capture log output and search it for `@`.

---

## File Structure

```
services/platform-api/
├─ src/platform_api/
│  ├─ shared/http.py                 ApiError, error handler, current_member, require_terms
│  ├─ shared/clock.py                add_months, utcnow
│  ├─ shared/ratelimit.py            RateLimiter port, InMemoryRateLimiter
│  ├─ entitlements/models.py         Entitlement, Contact, SourceState, Access, Reason, Decision, Campaign, GrantPolicy, ...
│  ├─ entitlements/runtime.py        Runtime (store, key, bus), set_runtime, get_runtime
│  ├─ entitlements/store.py          EntitlementStore port, InMemoryStore
│  ├─ entitlements/keys.py           ContactKey port, LocalContactKey
│  ├─ entitlements/access.py         access_from, decision_for, reasons_from, TIERS          (pure)
│  ├─ entitlements/reconcile.py      plan, Guard, ReconcilePlan, ReconcileReport             (pure) + apply
│  ├─ entitlements/campaigns.py      grants_from, campaign_state                             (pure) + apply
│  ├─ entitlements/public.py         the functions of contracts §3
│  ├─ entitlements/http.py           GET /v1/public/campaigns/{slug}, GET /v1/me/entitlements
│  ├─ identity/models.py  runtime.py  store.py  provider.py  public.py  http.py
│  ├─ admin/public.py  http.py  client.py      owner routes and the CLI's HTTP client
│  ├─ adapters/firestore_*.py  kms.py  firebase.py   cloud versions of the ports (Task 9)
│  └─ cli.py  main.py  settings.py              extended
└─ tests/
   ├─ fixtures/people.py             the eight people and builders for their records
   ├─ entitlements/test_contacts.py  test_access.py  test_claim_grant.py  test_reconcile.py  test_campaigns.py
   ├─ identity/test_sessions.py  test_http_member.py
   ├─ admin/test_admin.py  test_cli_client.py
   └─ integration/test_firestore_stores.py
```

---

### Task 1: Records, ports, and one contact per person

**Files:**
- Create: `shared/http.py`, `shared/clock.py`, `entitlements/models.py`, `runtime.py`, `store.py`, `keys.py`; `tests/fixtures/__init__.py`, `tests/fixtures/people.py`, `tests/entitlements/__init__.py`, `tests/entitlements/test_contacts.py`, `tests/test_http_errors.py`
- Modify: `entitlements/public.py`, `app.py` (install the error handler)

**Interfaces:**
- Produces, in `entitlements/models.py` (all frozen Pydantic models; every datetime timezone-aware):

```python
Source = Literal["substack_stripe", "substack_roster", "platform_stripe", "payhip", "grant"]
Status = Literal["active", "grace", "expired", "revoked"]
PlanInterval = Literal["month", "year"]

class Entitlement(BaseModel):
    entitlement_id: str
    contact_id: str
    member_uid: str | None
    grant: str                                  # "tier:paid", "status:substack_paid", "item:<sku>"
    source: Source
    source_ref: str
    access_scope: Literal["substack+platform", "platform_only"] | None
    plan_interval: PlanInterval | None
    valid_from: datetime | None
    valid_until: datetime | None
    status: Status
    updated_at: datetime
    updated_by: str                             # "run:<run_id>", "member:<uid>", "owner:<account id>", "policy:<slug>"

class SourceState(BaseModel): ...               # exactly as on the contracts page; email: str = Field(repr=False)

class ChannelsPatch(BaseModel):                 # what a caller knows about one channel; unset fields change nothing
    substack: dict[str, object] | None = None
    stripe: dict[str, object] | None = None
    platform: dict[str, object] | None = None

class Contact(BaseModel):
    contact_id: str
    key_version: str
    email: str = Field(repr=False)
    channels: dict[str, dict[str, object]]
    invite: dict[str, object]                   # {"campaign": slug or None, "state": "none" | "accepted"}
    created_at: datetime
    updated_at: datetime

class AuditEntry(BaseModel):
    at: datetime
    actor: str                                  # same form as Entitlement.updated_by
    action: str                                 # "entitlement.created", ".updated", ".ended", ".claimed", ".granted", ".revoked",
                                                # "campaign.written", "launch.switched", "admin.read"
    subject: str                                # an id, never an address
    reason: str | None
    evidence: dict[str, str]                    # ids only

def entitlement_id(source: str, source_ref: str, contact_id: str, grant: str) -> str: ...
def normalise_email(value: str) -> str: ...     # strip, then lower(); raises ValueError unless exactly one "@" with text on both sides
```

- `entitlements/keys.py`: `class ContactKey(Protocol): version: str; def mac(self, data: bytes) -> bytes: ...` and `LocalContactKey(secret: bytes, version: str = "local")` (HMAC-SHA256 with `hmac`).
- `entitlements/store.py`: `EntitlementStore` (Protocol) and `InMemoryStore`, with exactly these methods. Later tasks add campaign and config methods to the same port.

```python
def get_contact(self, contact_id: str) -> Contact | None: ...
def put_contact(self, contact: Contact) -> None: ...
def contact_ids_for_member(self, uid: str) -> list[str]: ...             # contacts whose channels.platform.member_uid is uid
def entitlements_for_contacts(self, contact_ids: Sequence[str]) -> list[Entitlement]: ...
def entitlements_for_member(self, uid: str) -> list[Entitlement]: ...    # member_uid == uid
def entitlements_by_source(self, source: Source) -> list[Entitlement]: ...
def get_entitlement(self, entitlement_id: str) -> Entitlement | None: ...
def write(self, contact_id: str, entitlements: Sequence[Entitlement], audit: Sequence[AuditEntry]) -> None: ...
    # one atomic unit per contact: all of it or none
def create_if_absent(self, entitlement: Entitlement, audit: AuditEntry) -> bool: ...   # False when the id already exists
def audit_for(self, subject: str) -> list[AuditEntry]: ...
```

- `entitlements/runtime.py`: `@dataclass class Runtime: store: EntitlementStore; key: ContactKey; bus: EventBus`, `set_runtime(runtime) -> None`, `get_runtime() -> Runtime` (raises `RuntimeError("entitlements runtime is not configured")`). `tests/conftest.py` gains a fixture `ent` that sets a fresh `Runtime(InMemoryStore(), LocalContactKey(b"test"), InMemoryBus())` and returns it.
- `entitlements/public.py`: `contact_id_for(email: str) -> str`, `upsert_contact(email: str, channels: ChannelsPatch) -> str` (creates the contact with `email` as first seen, or merges the patch into `channels`; never rewrites `email`), and re-exports the models other modules need.
- `shared/http.py`: `class ApiError(Exception)` with `status`, `code`, `message`, `retry_after: int | None = None`, `reason: str | None = None`; `install_error_handlers(app)` so that an `ApiError` and FastAPI's own validation error produce the body of contracts §1 (`{"error": {"code", "message", "retry_after"}}`, plus `"reason"` when set; validation gives 422 `validation_failed` with a message that names fields and never echoes values; an unknown route gives 404 `not_found` in the same shape). `create_app` also sets `app.state.settings = settings`, which later tasks read.
- `shared/clock.py`: `add_months(start: datetime, months: int) -> datetime` (same day of the month, or the month's last day when it has no such day) and `utcnow() -> datetime`. Route handlers and jobs get the time by calling `clock.utcnow()` through the module, so a test can replace it. `tests/conftest.py` gains an autouse fixture that sets it to `T0`: no test depends on the real date.
- `tests/__init__.py` is created if absent, so that test modules can import helpers from each other.
- `tests/fixtures/people.py`: `EMAIL: dict[str, str]` (`ana` … `hal`, `<name>@example.org`) and `T0 = datetime(2026, 11, 20, tzinfo=UTC)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/entitlements/test_contacts.py
import logging

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import ChannelsPatch, entitlement_id, normalise_email
from tests.fixtures.people import EMAIL


def test_one_person_one_contact_whatever_the_spelling(ent):
    assert ent_api.contact_id_for(" Ana@Example.ORG ") == ent_api.contact_id_for(EMAIL["ana"])
    assert len(ent_api.contact_id_for(EMAIL["ana"])) == 32
    assert ent_api.contact_id_for(EMAIL["ana"]) != ent_api.contact_id_for(EMAIL["bo"])


@pytest.mark.parametrize("bad", ["", "ana", "@example.org", "ana@", "a@b@c"])
def test_a_value_that_is_not_an_address_is_refused_without_being_repeated(bad):
    with pytest.raises(ValueError) as err:
        normalise_email(bad)
    assert bad == "" or bad not in str(err.value)


def test_upsert_keeps_the_first_address_and_merges_channels(ent):
    cid = ent_api.upsert_contact("Ana@Example.org", ChannelsPatch(stripe={"has_substack_subscription": True}))
    again = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    contact = ent.store.get_contact(cid)
    assert again == cid and contact.email == "Ana@Example.org" and contact.key_version == "local"
    assert contact.channels["stripe"] == {"has_substack_subscription": True}
    assert ent.store.contact_ids_for_member("u-ana") == [cid]


def test_a_contact_never_prints_its_address(ent, caplog):
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch())
    with caplog.at_level(logging.INFO):
        logging.getLogger("t").info("contact %r %s", ent.store.get_contact(cid), ent.store.get_contact(cid))
    assert "@" not in caplog.text


def test_entitlement_ids_are_deterministic_and_separate_people():
    a = entitlement_id("substack_stripe", "sub_1", "c1", "tier:paid")
    assert a == entitlement_id("substack_stripe", "sub_1", "c1", "tier:paid") and len(a) == 32
    assert a != entitlement_id("substack_stripe", "sub_1", "c2", "tier:paid")
```

```python
# tests/test_http_errors.py
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from platform_api.app import create_app
from platform_api.settings import Settings
from platform_api.shared.http import ApiError


class Body(BaseModel):
    note: str


def client():
    app = create_app(Settings())
    extra = APIRouter()

    @extra.get("/v1/_boom")
    def boom():
        raise ApiError(429, "rate_limited", "Try again later.", retry_after=30)

    @extra.post("/v1/_body")
    def body(b: Body):
        return {}

    app.include_router(extra)
    return TestClient(app)


def test_an_api_error_has_the_contract_shape():
    r = client().get("/v1/_boom")
    assert r.status_code == 429
    assert r.json() == {"error": {"code": "rate_limited", "message": "Try again later.", "retry_after": 30}}


def test_a_bad_body_is_validation_failed_and_does_not_echo_values():
    r = client().post("/v1/_body", json={"note": {"secret": "ana@example.org"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    assert "@" not in r.text and "note" in r.json()["error"]["message"]
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/entitlements tests/test_http_errors.py -v`
Expected: FAIL, `No module named 'platform_api.entitlements.models'`.

- [ ] **Step 3: Implement**

`InMemoryStore.write` and `create_if_absent` copy the models they are given, so a test cannot change stored state by accident.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 11 new tests pass (the parametrised one counts five); all earlier tests still pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: entitlement records, store and key ports, one contact per person, contract error shape"
```

---

### Task 2: What a member may open

**Files:**
- Create: `entitlements/access.py`, `tests/entitlements/test_access.py`
- Modify: `entitlements/models.py`, `entitlements/public.py`, `tests/fixtures/people.py`

**Interfaces:**
- Produces, in `models.py`: `Reason` and `Access` exactly as contracts §2 (0.4: `Reason` has `plan_interval`), and `Decision(allowed: bool, reason: Literal["paid_required", "purchase_required"] | None)`.
- In `access.py`, all pure:

```python
TIERS: Mapping[str, tuple[str, ...]] = {"free": ("overview", "library", "account"),
                                        "paid": ("overview", "library", "account", "research", "guides")}

def is_live(e: Entitlement, now: datetime) -> bool: ...
def access_from(entitlements: Sequence[Entitlement], now: datetime) -> Access: ...
def decision_for(entitlements: Sequence[Entitlement], item_access: Literal["paid", "free_members", "purchase_only"],
                 sku: str, now: datetime) -> Decision: ...
def label_for(e: Entitlement) -> str: ...
```

- Rules:
  - `is_live`: status is `active` or `grace`; and, **only for `source == "grant"`**, `valid_until` is `None` or later than `now`. A source-backed entitlement whose date has passed is still live (Rule 1: the date is a prompt to re-check).
  - `access_from`: tier is `paid` when any live entitlement has grant `tier:paid`, else `free`. `items` are the skus of live `item:<sku>` grants, sorted. `reasons` lists **every** entitlement that is live, plus `grant`-sourced ones that ended in the last 30 days (status as stored, or `expired` when its date has passed), newest `valid_until` last. A `status:` grant gives no tier and no item, and is listed.
  - `label_for`: `substack_status` for a grant starting `status:`; `launch_grant` for source `grant` with `source_ref` starting `campaign:`; `owner_grant` for any other source `grant`; `substack_subscription` for the two Substack sources; `platform_subscription` for `platform_stripe`; `purchase` for `payhip`.
  - `decision_for`: `free_members` → allowed. `paid` → allowed when the tier is paid or the sku is among the items, else `paid_required`. `purchase_only` → allowed only when the sku is among the items, else `purchase_required`.
- `public.py`: `access_for(uid: str, now: datetime) -> Access` loads `entitlements_for_member(uid)` together with `entitlements_for_contacts(contact_ids_for_member(uid))`, removes duplicates by id, and calls `access_from`. `can_open(uid: str, sku: str, now: datetime) -> Decision` takes the item's access from a port added by the Library lane; until then it accepts an optional keyword `item_access` and raises `LookupError` when neither is available.
- `tests/fixtures/people.py` gains `record(name: str, kind: str, **over) -> Entitlement` (contact id `c-<name>` unless given; a `launch_grant` has `source_ref` `campaign:founding` and the id that `entitlement_id` gives for it), where `kind` is one of `"stripe_year"`, `"stripe_month_status"`, `"roster_status"`, `"launch_grant"`, `"owner_grant"`, `"item"`, and `holdings(name: str) -> list[Entitlement]` giving each person's records under the settings in force (annual → `tier:paid`; monthly and no-interval → `status:substack_paid`): `ana` = stripe_year + launch_grant (until `T0` + 6 months); `bo`, `ed` = none; `cy` = stripe_month_status started after the cut-off; `di` = roster_status; `fay` = stripe_year with status `expired` + launch_grant; `gus` = stripe_year + roster_status; `hal` = stripe_month_status. `people.py` also defines `CUT_OFF = T0 - timedelta(days=30)`. Defaults of `record()` per kind: `stripe_year` → source `substack_stripe`, grant `tier:paid`, interval `year`, `source_ref` `sub_<name>`, `valid_from` `T0` − 200 days, `valid_until` `T0` + 165 days; `stripe_month_status` → the same with grant `status:substack_paid`, interval `month`, and for `cy` `valid_from` `T0` − 5 days; `roster_status` → source `substack_roster`, `source_ref` `roster`, grant `status:substack_paid`, no interval, `valid_from` `T0` − 200 days; `launch_grant` → source `grant`, `source_ref` `campaign:founding`, grant `tier:paid`, `valid_from` `T0`, `valid_until` `add_months(T0, 6)`; `owner_grant` → source `grant`, `source_ref` `owner:test`, grant `tier:paid`, no end; `item` → source `payhip`, `source_ref` `sale_<name>`, grant `item:sample`. Status is `active` and `member_uid` is empty unless given. `record()` computes `entitlement_id` **after** applying the overrides.

- [ ] **Step 1: Write the failing tests**

```python
# tests/entitlements/test_access.py
from datetime import timedelta

import pytest

from platform_api.entitlements.access import access_from, decision_for, is_live, label_for
from tests.fixtures.people import T0, holdings, record


@pytest.mark.parametrize(("name", "tier"), [("ana", "paid"), ("bo", "free"), ("cy", "free"), ("di", "free"),
                                             ("fay", "paid"), ("gus", "paid"), ("hal", "free")])
def test_tiers_of_the_fixture_people(name, tier):
    assert access_from(holdings(name), T0).tier == tier


def test_sections_follow_the_tier():
    assert access_from([], T0).sections == ["overview", "library", "account"]
    assert "research" in access_from(holdings("ana"), T0).sections


def test_a_status_grant_unlocks_nothing_and_is_explained():
    access = access_from(holdings("hal"), T0)
    assert (access.tier, access.items) == ("free", [])
    assert [(r.label, r.plan_interval, r.status) for r in access.reasons] == [("substack_status", "month", "active")]


def test_a_grant_ends_on_its_date_without_waiting_for_a_sweep():
    grant = record("fay", "launch_grant", valid_until=T0 + timedelta(days=1))
    assert is_live(grant, T0) and not is_live(grant, T0 + timedelta(days=1))
    after = access_from([grant], T0 + timedelta(days=2))
    assert after.tier == "free" and [r.status for r in after.reasons] == ["expired"]


def test_a_source_backed_record_stays_live_past_its_date():
    assert is_live(record("ana", "stripe_year", valid_until=T0 - timedelta(days=3)), T0)


def test_grace_is_live_and_revoked_is_not():
    assert access_from([record("ana", "stripe_year", status="grace")], T0).tier == "paid"
    assert access_from([record("ana", "owner_grant", status="revoked")], T0).tier == "free"


def test_labels():
    assert [label_for(record("ana", k)) for k in ("stripe_year", "launch_grant", "owner_grant", "roster_status", "item")] == [
        "substack_subscription", "launch_grant", "owner_grant", "substack_status", "purchase"]


@pytest.mark.parametrize(
    ("holder", "item_access", "allowed", "reason"),
    [("ana", "paid", True, None), ("bo", "paid", False, "paid_required"), ("bo", "free_members", True, None),
     ("ana", "purchase_only", False, "purchase_required"), ("buyer", "purchase_only", True, None), ("buyer", "paid", True, None)],
)
def test_decisions(holder, item_access, allowed, reason):
    held = [record("bo", "item", grant="item:map-1")] if holder == "buyer" else holdings(holder)
    decision = decision_for(held, item_access, "map-1", T0)
    assert (decision.allowed, decision.reason) == (allowed, reason)
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/entitlements/test_access.py -v`
Expected: FAIL, `No module named 'platform_api.entitlements.access'`.

- [ ] **Step 3: Implement `access.py`, the fixtures, and `access_for` / `can_open`**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 19 new tests pass (7 tiers, 6 decisions, 6 others).

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: access from the union of live entitlements; decisions per item"
```

---

### Task 3: Claims, owner grants and the audit trail

**Files:**
- Create: `tests/entitlements/test_claim_grant.py`
- Modify: `entitlements/public.py`

**Interfaces:**
- Produces:

```python
def claim_for_member(uid: str, contact_id: str) -> list[str]: ...
def grant(contact_id: str, grant: str, valid_until: datetime | None, reason: str, actor: str, now: datetime) -> str: ...
def revoke(entitlement_id: str, reason: str, actor: str, now: datetime) -> None: ...
```

- `now` is added to the two signatures of the contracts page (Global Constraints: time is passed in). This plan's pull request notes it on the contracts page.
- `claim_for_member`: sets `member_uid` on every entitlement under the contact that has none; writes `channels.platform.member_uid` and `registered_at` on the contact if absent; one `entitlement.claimed` audit entry per record; returns the ids it claimed. Calling it again claims nothing. It never takes a record that another member has claimed, and it claims nothing (returns `[]`) when the contact's `channels.platform.member_uid` is another member's uid.
- `grant`: refuses an empty `reason` (`ValueError`), a `grant` that does not start with `tier:` or `item:`, and a `valid_until` that is not later than `now`. Creates a `grant`-sourced entitlement with `source_ref = "owner:" + sha256(reason + now.isoformat())[:12]`, status `active`, `valid_from = now`, `member_uid` taken from the contact when it has one. Publishes `membership.entitlement.granted` with `contact_id`, `entitlement_id`, `grant`, `source: "grant"`, `source_ref`.
- `revoke`: only a `grant`-sourced entitlement can be revoked (`ValueError` otherwise: a source ends only its own records, Rule 2). Sets status `revoked`. An unknown id raises `LookupError`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/entitlements/test_claim_grant.py
from datetime import timedelta

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import ChannelsPatch
from tests.fixtures.people import EMAIL, T0, record


def seeded(runtime, name, *kinds):
    cid = ent_api.upsert_contact(EMAIL[name], ChannelsPatch())
    runtime.store.write(cid, [record(name, k, contact_id=cid) for k in kinds], [])
    return cid


def test_first_sign_in_claims_what_was_waiting(ent):
    cid = seeded(ent, "ana", "stripe_year")
    claimed = ent_api.claim_for_member("u-ana", cid)
    assert len(claimed) == 1 and ent.store.get_entitlement(claimed[0]).member_uid == "u-ana"
    assert ent_api.claim_for_member("u-ana", cid) == []
    assert ent_api.access_for("u-ana", T0).tier == "paid"


def test_a_claim_sticks_and_cannot_be_taken(ent):
    cid = seeded(ent, "ana", "stripe_year")
    ent_api.claim_for_member("u-ana", cid)
    assert ent_api.claim_for_member("u-other", cid) == []
    assert ent.store.entitlements_for_member("u-other") == []


def test_an_owner_grant_is_live_until_its_date_and_is_audited(ent):
    cid = seeded(ent, "di")
    ent_api.claim_for_member("u-di", cid)
    eid = ent_api.grant(cid, "tier:paid", T0 + timedelta(days=30), "complimentary reader, reviewed", "owner:acc-1", T0)
    assert ent_api.access_for("u-di", T0).tier == "paid"
    assert ent_api.access_for("u-di", T0 + timedelta(days=31)).tier == "free"
    entry = ent.store.audit_for(eid)[-1]
    assert (entry.action, entry.actor, entry.reason) == ("entitlement.granted", "owner:acc-1", "complimentary reader, reviewed")
    assert [e.type.rsplit(".", 3)[-3:] for e in ent.bus.published] == [["membership", "entitlement", "granted"]]


@pytest.mark.parametrize(("grant", "until", "reason"), [("tier:paid", T0 + timedelta(days=1), ""),
                                                        ("status:substack_paid", T0 + timedelta(days=1), "r"),
                                                        ("tier:paid", T0, "r")])
def test_a_grant_without_reason_with_a_wrong_name_or_already_over_is_refused(ent, grant, until, reason):
    with pytest.raises(ValueError):
        ent_api.grant(seeded(ent, "di"), grant, until, reason, "owner:acc-1", T0)


def test_only_grants_can_be_revoked(ent):
    cid = seeded(ent, "ana", "stripe_year")
    eid = ent_api.grant(cid, "tier:paid", None, "r", "owner:acc-1", T0)
    ent_api.revoke(eid, "mistake", "owner:acc-1", T0)
    assert ent.store.get_entitlement(eid).status == "revoked"
    stripe_id = ent.store.entitlements_by_source("substack_stripe")[0].entitlement_id
    with pytest.raises(ValueError):
        ent_api.revoke(stripe_id, "no", "owner:acc-1", T0)
    with pytest.raises(LookupError):
        ent_api.revoke("nope", "no", "owner:acc-1", T0)
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/entitlements/test_claim_grant.py -v`
Expected: FAIL, `module 'platform_api.entitlements.public' has no attribute 'claim_for_member'`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 7 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: claims that stick, owner grants and revocation, audited"
```

---

### Task 4: Applying what a source says

**Files:**
- Create: `entitlements/reconcile.py`, `tests/entitlements/test_reconcile.py`
- Modify: `entitlements/public.py`

**Interfaces:**
- Produces, in `reconcile.py`:

```python
class Guard(BaseModel):
    max_ends: int = 5
    max_fraction: float = 0.2

class Action(BaseModel):
    kind: Literal["create", "update", "end", "move"]
    entitlement: Entitlement                     # the record as it will be after the action
    email: str | None = Field(default=None, repr=False, exclude=True)   # set for "create" and "move", used once to upsert the contact; never dumped
    evidence_source_ref: str

class ReconcilePlan(BaseModel):
    actions: list[Action]
    unchanged: int
    unseen: list[str]                            # entitlement ids
    blocked: bool
    ends: int
    live_before: int

class ReconcileReport(BaseModel):
    run_id: str
    created: int; updated: int; ended: int; moved: int; unchanged: int; unseen: int
    tier_changes: int
    grants_created: int
    blocked: bool

def plan(existing: Sequence[Entitlement], resolved: Sequence[tuple[str, SourceState]], guard: Guard, now: datetime) -> ReconcilePlan: ...
```

- `resolved` pairs each state with the contact id of its address. `existing` is every entitlement of the sources the caller is reconciling.
- Rules of `plan`:
  - The record for a state is found by its `entitlement_id` first. Only for `substack_stripe` and `platform_stripe`, whose reference is a subscription id, it is then looked for by `(source, source_ref)`; when several records share a reference (after a move), the one that is not ended is taken. A roster state's reference is the fixed word `roster`, so roster records are found by id only.
  - A record with the same source, reference and contact but **another grant name** (the owner changed what a plan is recorded as): one `move` that ends the old record and creates the new one.
  - No record, state `active` or `grace` → `create` (`valid_from = started_at`, `plan_interval`, `access_scope`, `valid_until` from the state; `member_uid` empty). No record, state `expired` → nothing.
  - A record under the **same** contact: fields differ → `update`; state `expired` and the record is live → `end` (status `expired`, `valid_until = provider_time`); a state `active` for a record that is `expired` → `update` back to `active` (same subscription reactivated); nothing differs → counted in `unchanged`.
  - A record under **another** contact (the address changed at the source): claimed (`member_uid` set) → treated as the same record, updated in place, the contact is not changed (Rule 4). Unclaimed → one `move`: the old record is ended and a new one is created under the new contact. A move is not counted as an end, but moves between contacts have the same limit as ends: more of them than the guard allows blocks the plan (a changed contact key would otherwise move every record unchecked).
  - A `revoked` record is never changed.
  - `unseen`: every existing record that no state referred to. Nothing is done to it.
  - `ends` counts `end` actions on grants starting `tier:` or `status:`. `live_before` counts live existing records with such grants. The plan is `blocked`, with `actions == []`, when `ends > max(guard.max_ends, guard.max_fraction * live_before)`.
  - Two states with the same `(source, source_ref)` for a Stripe source, or the same `(source, source_ref, contact)` for the roster → `ValueError` naming the source and the reference.
- `public.py`:
  - `public.py` re-exports the models other modules may use: `SourceState`, `Guard`, `Entitlement`, `ChannelsPatch`, `Access`, `Reason`, `LaunchConfig`, `Campaign`, `AuditEntry` (added on 2026-11-23).
  - `existing_for(sources: Sequence[Source]) -> list[Entitlement]`: every record of those sources, whatever its status. The Commerce lane loads `existing` with it (added on 2026-11-23).
  - `plan_reconcile(existing, states, guard, now) -> ReconcilePlan` resolves each address with `contact_id_for`, then calls `plan`. (`now` is added to the contract signature.)
  - `apply_plan(plan, run_id, now) -> ReconcileReport`: a blocked plan writes nothing. Otherwise, grouped by contact: record the tier of the contact's member (if any) before; upsert the contact for `create` and `move`; one `store.write` per contact with an audit entry per action (`actor = "run:<run_id>"`); set `member_uid` on a created record when the contact already has a member; call `apply_grant_policies(contact_id, now)` when the contact has a member (it exists from Task 5; until then a module-level hook that returns `[]`); compare the tier after, and publish one `membership.tier.changed` (`member_uid`, `from`, `to`, `run_id`) when it differs.

- [ ] **Step 1: Write the failing tests**

```python
# tests/entitlements/test_reconcile.py
from datetime import timedelta

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import SourceState
from platform_api.entitlements.reconcile import Guard
from tests.fixtures.people import EMAIL, T0


def state(name, ref, status="active", grant="tier:paid", interval="year", email=None, source="substack_stripe"):
    return SourceState(source=source, source_ref=ref, email=email or EMAIL[name], grant=grant, status=status,
                       started_at=T0 - timedelta(days=200), valid_until=T0 + timedelta(days=165), plan_interval=interval,
                       access_scope="substack+platform", provider_time=T0)


def run(ent, states, guard=None, run_id="r1"):
    existing = ent.store.entitlements_by_source("substack_stripe")
    plan = ent_api.plan_reconcile(existing, states, guard or Guard(), T0)
    return plan, ent_api.apply_plan(plan, run_id, T0)


def test_first_run_creates_and_second_run_changes_nothing(ent):
    states = [state("ana", "sub_a"), state("hal", "sub_h", grant="status:substack_paid", interval="month")]
    _, first = run(ent, states)
    plan, second = run(ent, states, run_id="r2")
    assert (first.created, second.created, second.updated, second.ended, second.unchanged) == (2, 0, 0, 0, 2)
    record = ent.store.entitlements_by_source("substack_stripe")[0]
    assert record.valid_from == T0 - timedelta(days=200) and record.member_uid is None


def test_an_expired_state_ends_only_its_own_record(ent):
    run(ent, [state("fay", "sub_f"), state("ana", "sub_a")])
    cid = ent_api.contact_id_for(EMAIL["fay"])
    ent_api.grant(cid, "tier:paid", T0 + timedelta(days=90), "launch", "owner:acc-1", T0)
    _, report = run(ent, [state("fay", "sub_f", status="expired"), state("ana", "sub_a")], run_id="r2")
    by_source = {e.source: e.status for e in ent.store.entitlements_for_contacts([cid])}
    assert report.ended == 1 and by_source == {"substack_stripe": "expired", "grant": "active"}


def test_a_record_the_source_did_not_mention_is_left_alone_and_reported(ent):
    run(ent, [state("ana", "sub_a"), state("gus", "sub_g")])
    plan, report = run(ent, [state("ana", "sub_a")], run_id="r2")
    assert (report.ended, report.unseen, len(plan.unseen)) == (0, 1, 1)
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_the_guard_blocks_a_run_that_would_end_too_many(ent):
    names = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]
    run(ent, [state(n, f"sub_{n}") for n in names])
    plan, report = run(ent, [state(n, f"sub_{n}", status="expired") for n in names[:6]], run_id="r2")
    assert plan.blocked and plan.actions == [] and (plan.ends, plan.live_before) == (6, 8)
    assert report.blocked and report.ended == 0
    assert all(e.status == "active" for e in ent.store.entitlements_by_source("substack_stripe"))


def test_five_ends_are_allowed(ent):
    names = ["ana", "cy", "fay", "gus", "hal", "bo", "di", "ed"]
    run(ent, [state(n, f"sub_{n}") for n in names])
    plan, report = run(ent, [state(n, f"sub_{n}", status="expired") for n in names[:5]], run_id="r2")
    assert not plan.blocked and report.ended == 5


def test_a_tier_change_is_one_event_for_a_member_and_none_for_a_stranger(ent):
    run(ent, [state("ana", "sub_a"), state("bo", "sub_b")])
    ent_api.claim_for_member("u-ana", ent_api.contact_id_for(EMAIL["ana"]))
    ent.bus.published.clear()
    run(ent, [state("ana", "sub_a", status="expired"), state("bo", "sub_b", status="expired")], run_id="r2")
    changed = [e for e in ent.bus.published if e.type.endswith("membership.tier.changed")]
    assert [(e.data["member_uid"], e.data["from"], e.data["to"]) for e in changed] == [("u-ana", "paid", "free")]


def test_an_address_changed_at_the_source_moves_an_unclaimed_record(ent):
    run(ent, [state("ed", "sub_e")])
    _, report = run(ent, [state("ed", "sub_e", email="ed.other@example.org")], run_id="r2")
    old = ent.store.entitlements_for_contacts([ent_api.contact_id_for(EMAIL["ed"])])
    new = ent.store.entitlements_for_contacts([ent_api.contact_id_for("ed.other@example.org")])
    assert (report.moved, report.ended) == (1, 0) and [e.status for e in old] == ["expired"] and [e.status for e in new] == ["active"]


def test_a_claimed_record_stays_with_its_member_when_the_address_changes(ent):
    run(ent, [state("ana", "sub_a")])
    cid = ent_api.contact_id_for(EMAIL["ana"])
    ent_api.claim_for_member("u-ana", cid)
    _, report = run(ent, [state("ana", "sub_a", email="ana.new@example.org", status="grace")], run_id="r2")
    kept = ent.store.entitlements_for_member("u-ana")
    assert (report.moved, report.updated) == (0, 1) and [(e.contact_id, e.status) for e in kept] == [(cid, "grace")]


def test_a_reactivated_subscription_becomes_active_again(ent):
    run(ent, [state("ana", "sub_a")])
    run(ent, [state("ana", "sub_a", status="expired")], run_id="r2")
    _, report = run(ent, [state("ana", "sub_a")], run_id="r3")
    assert report.updated == 1 and ent.store.entitlements_by_source("substack_stripe")[0].status == "active"


def test_the_same_reference_twice_in_one_run_is_refused(ent):
    with pytest.raises(ValueError, match="sub_a"):
        ent_api.plan_reconcile([], [state("ana", "sub_a"), state("bo", "sub_a")], Guard(), T0)


def test_a_plan_and_a_report_never_print_an_address(ent):
    plan = ent_api.plan_reconcile([], [state("ana", "sub_a")], Guard(), T0)
    assert "@" not in repr(plan) and "@" not in ent_api.apply_plan(plan, "r1", T0).model_dump_json()
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/entitlements/test_reconcile.py -v`
Expected: FAIL, `No module named 'platform_api.entitlements.reconcile'`.

- [ ] **Step 3: Implement `reconcile.py`, `plan_reconcile`, `apply_plan`**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 11 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: plan and apply a source's current state, with unseen list and mass-change guard"
```

---

### Task 5: Campaigns and the launch grant

**Files:**
- Create: `entitlements/campaigns.py`, `entitlements/http.py` content, `tests/entitlements/test_campaigns.py`
- Modify: `entitlements/models.py`, `store.py`, `public.py`

**Interfaces:**
- Produces, in `models.py`:

```python
class GrantPolicy(BaseModel):
    grant: Literal["tier:paid"]
    months: int | None                           # required when starts is "at_claim"
    starts: Literal["at_claim", "fixed"]
    fixed_until: datetime | None                 # required when starts is "fixed"
    requires_live_source: list[Source]
    paid_since_before: datetime | None
    plan_intervals: list[PlanInterval] | None

class Campaign(BaseModel):
    slug: str                                    # ^[a-z0-9-]{1,40}$ and not "default"
    audience: Literal["substack_paid", "substack_free", "public"]
    opens_at: datetime | None
    closes_at: datetime | None
    is_default: bool
    grant: GrantPolicy | None
    copy_: dict[str, str] = Field(alias="copy")  # headline, body, cta. The plain name would shadow BaseModel.copy; the model sets
                                                 # ConfigDict(populate_by_name=True), and stores and routes dump with by_alias=True
    counts: dict[str, int]                       # arrivals, recognised_paid, grants_created

class GrantSpec(BaseModel):
    campaign: str; contact_id: str; grant: str; valid_until: datetime; evidence_entitlement_id: str

class LaunchConfig(BaseModel):
    join_open: bool = False; library_open: bool = False; promotions_open: bool = False
    reconcile_max_age_seconds: int = 900
    required_terms_version: str = ""; required_privacy_version: str = ""
    substack_account_url: str = ""
```

- A policy's `requires_live_source` may not contain `grant` (validation error): a grant never earns another grant.
- `store.py` gains `get_campaign(slug)`, `list_campaigns()`, `put_campaigns(campaigns)`, `add_to_campaign_count(slug, key, by=1)`, `get_launch_config() -> LaunchConfig`, `put_launch_config(config)`.
- `campaigns.py`, pure: `campaign_state(campaign, config, now) -> Literal["scheduled", "open", "closed"]` (always `closed` while `join_open` is off; `scheduled` before `opens_at`; `closed` from `closes_at`) and `grants_from(entitlements, campaigns, config, now) -> list[GrantSpec]`.
- A grant is due from a campaign when all of these hold: the campaign's state is `open`; it has a policy; some **live** entitlement `e` has `e.source` in `requires_live_source`; `paid_since_before` is `None`, or `e.valid_from` is set and earlier than it; `plan_intervals` is `None`, or `e.plan_interval` is one of them; and no entitlement with the grant's id exists among `entitlements`, **whatever its status**. `valid_until` is `add_months(now, months)` or `fixed_until`. The grant belongs to `e.contact_id`. One spec per campaign and contact, however many records qualify.
- `public.py`: `campaign_by_slug(slug: str | None, now) -> Campaign` (unknown, `None` or `"default"` → the campaign with `is_default`; no default stored → `LookupError`); `grants_due(entitlements, campaigns, now)` (loads the config, calls `grants_from`); `apply_grant_policies(contact_id: str, now) -> list[str]` (no member on the contact → `[]`; otherwise creates each due grant with `store.create_if_absent`, `updated_by = "policy:<slug>"`, an audit entry whose `evidence` is `{"entitlement_id": <the qualifying record>, "campaign": <slug>}`, the count `grants_created`, and the event `membership.entitlement.granted`; returns the ids it created); `record_arrival(uid: str, campaign: Campaign, recognition: str) -> None` (ruling 2; counts start as an empty map and only the keys that were incremented exist). For the owner's routes of Task 8, also: `put_campaigns(campaigns: list[Campaign], actor: str) -> int` (keeps the counts of a slug that already exists), `list_campaigns() -> list[Campaign]`, `update_launch_config(patch: dict[str, object], actor: str) -> LaunchConfig`, `contact_view(contact_id: str, now) -> ContactView | None` (channels, whether a member exists, reasons with entitlement ids, audit entries; no address), `write_audit(entry: AuditEntry) -> None` and `audit_for(subject: str) -> list[AuditEntry]`.
- `entitlements/http.py`: `GET /v1/public/campaigns/{slug}` → `{slug, audience, state, copy}` with `slug: null` when the default was substituted. `GET /v1/me/entitlements` is added in Task 7.

- [ ] **Step 1: Write the failing tests**

```python
# tests/entitlements/test_campaigns.py
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from platform_api.app import create_app
from platform_api.entitlements import public as ent_api
from platform_api.entitlements.campaigns import campaign_state, grants_from
from platform_api.entitlements.models import Campaign, ChannelsPatch, GrantPolicy, LaunchConfig
from platform_api.settings import Settings
from platform_api.shared.clock import add_months
from tests.fixtures.people import CUT_OFF, EMAIL, T0, holdings, record

POLICY = GrantPolicy(grant="tier:paid", months=6, starts="at_claim", fixed_until=None,
                     requires_live_source=["substack_stripe", "substack_roster"], paid_since_before=CUT_OFF, plan_intervals=["year"])
OPEN = LaunchConfig(join_open=True)
WIDE = POLICY.model_copy(update={"paid_since_before": None, "plan_intervals": None})


def campaign(slug="founding", **over):
    base = dict(slug=slug, audience="substack_paid", opens_at=T0 - timedelta(days=1), closes_at=T0 + timedelta(days=60),
                is_default=False, grant=POLICY, copy={"headline": "h", "body": "b", "cta": "c"}, counts={})
    return Campaign(**{**base, **over})


def due(name, held=None, c=None, config=OPEN, now=T0):
    return grants_from(held if held is not None else holdings(name)[:1], [c or campaign()], config, now)


def test_ana_gets_six_months_from_the_moment_of_the_claim():
    [spec] = due("ana")
    assert (spec.campaign, spec.grant, spec.valid_until) == ("founding", "tier:paid", add_months(T0, 6))


@pytest.mark.parametrize("name", ["bo", "cy", "di", "hal"])
def test_free_late_no_interval_and_monthly_readers_get_none(name):
    assert due(name, held=holdings(name)) == []


def test_gus_gets_exactly_one_from_two_qualifying_records():
    assert len(due("gus", held=holdings("gus"), c=campaign(grant=WIDE))) == 1


def test_evaluating_again_after_the_grant_exists_gives_nothing_even_when_it_has_ended():
    held = holdings("fay")                      # cancelled subscription + launch grant
    assert due("fay", held=held) == []
    ended = [e.model_copy(update={"status": "expired"}) for e in holdings("ana")]
    live_again = [record("ana", "stripe_year"), ended[1]]
    assert due("ana", held=live_again) == []


@pytest.mark.parametrize(("over", "config", "now", "state"), [
    ({}, LaunchConfig(join_open=False), T0, "closed"),
    ({"opens_at": T0 + timedelta(days=1)}, OPEN, T0, "scheduled"),
    ({}, OPEN, T0 + timedelta(days=61), "closed"),
])
def test_a_campaign_that_is_not_open_grants_nothing(over, config, now, state):
    c = campaign(**over)
    assert campaign_state(c, config, now) == state and due("ana", c=c, config=config, now=now) == []


def test_a_policy_without_cut_off_or_intervals_takes_every_paying_reader():
    wide = campaign(grant=WIDE)
    assert [len(due(n, held=holdings(n), c=wide)) for n in ("cy", "di", "hal")] == [1, 1, 1]


def test_applying_twice_creates_one_grant_and_only_for_a_member(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign(), campaign("members", audience="public", grant=None, is_default=True)])
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch())
    ent.store.write(cid, [e.model_copy(update={"contact_id": cid}) for e in holdings("ana")[:1]], [])
    assert ent_api.apply_grant_policies(cid, T0) == []                       # nobody has signed in
    ent_api.claim_for_member("u-ana", cid)
    first, second = ent_api.apply_grant_policies(cid, T0), ent_api.apply_grant_policies(cid, T0 + timedelta(days=3))
    assert len(first) == 1 and second == []
    stored = ent.store.get_entitlement(first[0])
    assert (stored.source, stored.source_ref, stored.valid_until, stored.member_uid) == ("grant", "campaign:founding", add_months(T0, 6), "u-ana")
    assert ent.store.audit_for(first[0])[0].evidence["entitlement_id"]
    assert ent.store.get_campaign("founding").counts["grants_created"] == 1


def test_an_unknown_slug_falls_back_to_the_default_campaign(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign(), campaign("members", audience="public", grant=None, is_default=True)])
    assert ent_api.campaign_by_slug("nope", T0).slug == "members" and ent_api.campaign_by_slug(None, T0).slug == "members"
    body = TestClient(create_app(Settings())).get("/v1/public/campaigns/nope").json()
    assert (body["slug"], body["state"], body["audience"]) == (None, "open", "public")
    assert TestClient(create_app(Settings())).get("/v1/public/campaigns/founding").json()["slug"] == "founding"


def test_an_arrival_is_counted_and_published_without_an_address(ent):
    ent.store.put_launch_config(OPEN)
    ent.store.put_campaigns([campaign()])
    cid = ent_api.upsert_contact(EMAIL["ana"], ChannelsPatch(platform={"member_uid": "u-ana"}))
    ent_api.record_arrival("u-ana", ent.store.get_campaign("founding"), "paid")
    assert ent.store.get_campaign("founding").counts == {"arrivals": 1, "recognised_paid": 1}
    assert ent.store.get_contact(cid).invite == {"campaign": "founding", "state": "accepted"}
    [event] = [e for e in ent.bus.published if e.type.endswith("membership.campaign.joined")]
    assert event.data == {"member_uid": "u-ana", "contact_id": cid, "campaign": "founding", "recognition": "paid"}
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/entitlements/test_campaigns.py -v`
Expected: FAIL, `No module named 'platform_api.entitlements.campaigns'`.

- [ ] **Step 3: Implement, and connect `apply_plan` to `apply_grant_policies`**

Add one test to `tests/entitlements/test_reconcile.py`, `test_a_member_recognised_by_a_run_gets_the_grant_and_one_tier_event`: `bo` has signed in (member `u-bo`, no records); a run brings an annual state for `bo` started before the cut-off; afterwards `u-bo` holds two live records (subscription and launch grant), the report says `grants_created == 1` and `tier_changes == 1`, and exactly one `membership.tier.changed` (`free` → `paid`) was published.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 14 new tests pass in `test_campaigns.py` (4 readers, 3 not-open cases, 7 others) and 1 new in `test_reconcile.py`.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: campaigns, grant policies evaluated on verified records, arrivals"
```

---

### Task 6: Sign-in, sessions and terms

**Files:**
- Create: `identity/models.py`, `runtime.py`, `store.py`, `provider.py`; `shared/ratelimit.py`; `tests/identity/__init__.py`, `tests/fixtures/launch.py` (`TERMS`), `tests/identity/conftest.py` (`world`), `tests/identity/test_sessions.py`
- Modify: `identity/public.py`, `identity/http.py`, `shared/http.py`, `settings.py`

**Interfaces:**
- Consumes: `entitlements.public` (`upsert_contact`, `claim_for_member`, `campaign_by_slug`, `apply_grant_policies`, `record_arrival`, `access_for`, the launch config through a new `entitlements.public.launch_config() -> LaunchConfig`).
- Produces:

```python
# identity/provider.py
class VerifiedIdentity(BaseModel):
    uid: str
    email: str = Field(repr=False)
    email_verified: bool
class InvalidToken(Exception): ...
class IdentityProvider(Protocol):
    def verify_id_token(self, token: str) -> VerifiedIdentity: ...            # raises InvalidToken
    def create_session_cookie(self, id_token: str, ttl: timedelta) -> str: ...
    def verify_session_cookie(self, cookie: str) -> str: ...                  # returns uid; raises InvalidToken when bad, expired or revoked
    def revoke_sessions(self, uid: str) -> None: ...
class FakeIdentityProvider: ...   # token "fake-token:<name>" → uid "u-<name>" for a name in the address table it was given, else InvalidToken;
                                  # unverified: set[str] of names whose address is not verified; cookie "fake-session:<uid>:<n>";
                                  # it remembers the cookies it issued and the uids it revoked, and accepts no other cookie

# identity/models.py
class Member(BaseModel): ...       # stored: uid, primary_contact_id, linked_contact_ids, email (repr=False), display_name, terms_accepted, joined_via, status, created_at, last_seen_at
class MemberView(BaseModel): ...   # the Member shape of contracts §2: uid, display_name, email_hint, terms{accepted, terms_version, privacy_version, required{...}}, joined_via, status
class MemberRef(BaseModel): uid: str; terms_ok: bool
class Join(BaseModel): ...         # contracts §2
class SessionResult(BaseModel): ...# contracts §2

# identity/public.py
class Unauthenticated(Exception): ...
class JoinClosed(Exception): ...
def resolve_session(id_token: str, campaign_slug: str | None, now: datetime) -> SessionResult: ...
def member_from_session(cookie: str) -> MemberRef: ...
def end_sessions(uid: str) -> None: ...
def member_view(uid: str) -> MemberView: ...
def accept_terms(uid: str, terms_version: str, privacy_version: str, now: datetime) -> MemberView: ...
def request_deletion(uid: str, now: datetime) -> None: ...
def member_count() -> int: ...
```

- `identity/store.py`: `MemberStore` port (`get`, `put`) and `InMemoryMemberStore`. `identity/runtime.py`: `Runtime(members, provider, bus: EventBus, session_ttl: timedelta, limiter: RateLimiter, request_refresh: Callable[[str, datetime], Literal["fresh", "started"]] | None, last_reconcile_at: Callable[[], datetime | None] | None)` (the `idn` fixture passes `ent.bus`, so one list holds every published event; when the Commerce lane wires `request_refresh`, its answer `already_running` is passed on as `started`) with `set_runtime` / `get_runtime`; fixture `idn` in `tests/conftest.py` builds it on top of `ent`.
- `resolve_session`, in this order: verify the token (`InvalidToken`, or `email_verified` false → `Unauthenticated`); if there is no member and `join_open` is off → `JoinClosed`; `upsert_contact` (with `platform={"member_uid": uid, "registered_at": now}` when the member is new, with an empty patch otherwise); create the member (`joined_via` = the campaign's slug) or update `last_seen_at`; `claim_for_member`; `apply_grant_policies`; on the first sign-in only, `record_arrival` (recognition is `paid` when the tier is paid **or** the member holds a live record from `substack_stripe` or `substack_roster`, else `free`; the same value is `join.recognition`) and the event `membership.member.registered` (`member_uid`, `contact_id`, `campaign`); when a refresh port is set and the last reconcile is older than `reconcile_max_age_seconds` (or unknown), call it and use its answer as `join.check`, else `"fresh"`; create the cookie with `timedelta(days=settings.session_ttl_days)`. `join.grant` is `{"created": true, "valid_until": …}` only when this call created one. A member whose status is `deletion_requested` cannot sign in (`Unauthenticated`).
- `settings.py` gains `session_ttl_days: int = 14` (refused above 14 or below 1: the provider's limit), `owner_accounts: Annotated[list[str], NoDecode] = []` with a validator that splits a comma-separated string (so the environment variable is `PLATFORM_OWNER_ACCOUNTS=id1,id2`, not JSON), `contact_key: str = ""`, `library_bucket: str = ""`.
- `email_hint`: the first character, `…@`, and the domain (`a…@example.org`).
- `accept_terms`: both versions must equal the config's required ones, else `ApiError(422, "validation_failed")`. `terms.accepted` in the view is true only when the stored versions equal the required ones, so changing a required version asks every member again.
- `shared/http.py` gains two FastAPI dependencies: `current_member` (reads `X-Member-Session`; missing or refused → `ApiError(401, "unauthenticated")`) and `member_with_terms` (as above, then 409 `terms_required` when `terms_ok` is false). `shared` may not import `identity`, so both take the lookup from `app.state.member_from_session`, which `create_app` sets from `identity.public`.
- `identity/http.py`, router: `POST /v1/session/resolve` (body `{id_token, campaign}`; `JoinClosed` → 403 `forbidden`; `Unauthenticated` → 401), `POST /v1/session/revoke`, `GET /v1/me` (→ `{member, access}`), `POST /v1/me/terms-acceptance`, `POST /v1/me/deletion-request`. The four of contracts §1 use `current_member`; every other member route in every module uses `member_with_terms`.
- `shared/ratelimit.py`: `class RateLimiter(Protocol): def hit(self, key: str, limit: int, window: timedelta, now: datetime) -> int | None` (returns seconds to wait, or `None` when allowed) and `InMemoryRateLimiter` (fixed windows). `POST /v1/session/resolve` is not limited here (the caller is `web`, not the public).

- [ ] **Step 1: Write the failing tests**

```python
# tests/identity/test_sessions.py
import logging
from datetime import timedelta

from tests.fixtures.launch import TERMS
from tests.fixtures.people import T0

# tests/fixtures/launch.py holds:
#     TERMS = LaunchConfig(join_open=True, required_terms_version="t1", required_privacy_version="p1")
#
# tests/identity/conftest.py holds the fixture (a fixture imported into a test module makes ruff report F811):
#     @pytest.fixture
#     def world(idn, ent):
#         ent.store.put_launch_config(TERMS)
#         ent.store.put_campaigns([campaign(), campaign("members", audience="public", grant=None, is_default=True)])
#         run(ent, [state("ana", "sub_a"), state("hal", "sub_h", grant="status:substack_paid", interval="month")])
#         return TestClient(create_app(Settings()))
#     with campaign, run and state imported from the two entitlement test modules.


def sign_in(client, name, slug=None):
    return client.post("/v1/session/resolve", json={"id_token": f"fake-token:{name}", "campaign": slug})


def test_ana_is_recognised_claims_her_record_and_gets_the_grant(world, ent):
    body = sign_in(world, "ana", "founding").json()
    assert (body["access"]["tier"], body["join"]["recognition"], body["join"]["campaign"]) == ("paid", "paid", "founding")
    assert body["join"]["grant"]["created"] is True and body["member"]["joined_via"] == "founding"
    assert body["member"]["email_hint"] == "a…@example.org" and "ana@" not in str(body)
    assert sorted(r["label"] for r in body["access"]["reasons"]) == ["launch_grant", "substack_subscription"]
    again = sign_in(world, "ana").json()
    assert again["join"]["grant"] is None and again["member"]["joined_via"] == "founding"
    assert ent.store.get_campaign("founding").counts["arrivals"] == 1


def test_the_grant_does_not_depend_on_the_link(world):
    assert sign_in(world, "ana", None).json()["join"]["grant"]["created"] is True


def test_bo_and_hal_are_free_and_hal_sees_his_plan(world):
    assert sign_in(world, "bo", "founding").json()["access"]["tier"] == "free"
    hal = sign_in(world, "hal").json()
    assert hal["access"]["tier"] == "free" and hal["join"]["grant"] is None and hal["join"]["recognition"] == "paid"
    assert [(r["label"], r["plan_interval"]) for r in hal["access"]["reasons"]] == [("substack_status", "month")]


def test_a_bad_token_and_an_unverified_address_are_refused(world, idn):
    assert world.post("/v1/session/resolve", json={"id_token": "garbage", "campaign": None}).status_code == 401
    idn.provider.unverified.add("bo")
    assert sign_in(world, "bo").status_code == 401


def test_a_closed_join_refuses_new_people_and_admits_members(world, ent):
    sign_in(world, "ana")
    ent.store.put_launch_config(TERMS.model_copy(update={"join_open": False}))
    assert sign_in(world, "ana").status_code == 200
    r = sign_in(world, "bo")
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_member_routes_need_a_good_cookie(world, idn):
    cookie = sign_in(world, "ana").json()["session"]["cookie"]
    assert world.get("/v1/me", headers={"X-Member-Session": cookie}).status_code == 200
    for bad in ({}, {"X-Member-Session": "garbage"}, {"X-Member-Session": cookie + "x"}):
        r = world.get("/v1/me", headers=bad)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    world.post("/v1/session/revoke", headers={"X-Member-Session": cookie})
    assert world.get("/v1/me", headers={"X-Member-Session": cookie}).status_code == 401


def test_terms_gate_every_member_route_except_the_four(world):
    cookie = {"X-Member-Session": sign_in(world, "ana").json()["session"]["cookie"]}
    assert world.get("/v1/me", headers=cookie).json()["member"]["terms"]["accepted"] is False
    gated = world.get("/v1/me/entitlements", headers=cookie)
    assert gated.status_code == 409 and gated.json()["error"]["code"] == "terms_required"
    assert world.post("/v1/me/terms-acceptance", headers=cookie, json={"terms_version": "old", "privacy_version": "p1"}).status_code == 422
    ok = world.post("/v1/me/terms-acceptance", headers=cookie, json={"terms_version": "t1", "privacy_version": "p1"})
    assert ok.json()["member"]["terms"]["accepted"] is True
    assert world.get("/v1/me/entitlements", headers=cookie).status_code == 200


def test_a_new_required_version_asks_again(world, ent):
    cookie = {"X-Member-Session": sign_in(world, "ana").json()["session"]["cookie"]}
    world.post("/v1/me/terms-acceptance", headers=cookie, json={"terms_version": "t1", "privacy_version": "p1"})
    ent.store.put_launch_config(TERMS.model_copy(update={"required_terms_version": "t2"}))
    assert world.get("/v1/me", headers=cookie).json()["member"]["terms"]["accepted"] is False


def test_a_deletion_request_ends_the_sessions_and_blocks_sign_in(world):
    cookie = {"X-Member-Session": sign_in(world, "bo").json()["session"]["cookie"]}
    assert world.post("/v1/me/deletion-request", headers=cookie).json() == {"status": "deletion_requested"}
    assert world.get("/v1/me", headers=cookie).status_code == 401 and sign_in(world, "bo").status_code == 401


def test_a_stale_reconcile_starts_a_check_when_the_port_exists(world, idn):
    calls = []
    idn.request_refresh = lambda uid, now: calls.append(uid) or "started"
    idn.last_reconcile_at = lambda: T0 - timedelta(hours=2)
    assert sign_in(world, "bo").json()["join"]["check"] == "started" and calls == ["u-bo"]
    idn.last_reconcile_at = lambda: T0
    assert sign_in(world, "bo").json()["join"]["check"] == "fresh" and calls == ["u-bo"]


def test_no_address_reaches_the_log_or_an_event(world, ent, caplog):
    with caplog.at_level(logging.DEBUG):
        sign_in(world, "ana", "founding")
        world.post("/v1/session/resolve", json={"id_token": "fake-token:nobody", "campaign": None})
    assert "@" not in caplog.text and all("@" not in e.model_dump_json() for e in ent.bus.published)
```

`GET /v1/me/entitlements` is used by one test above: add it in this task as a three-line route in `entitlements/http.py` (`{"entitlements": access_for(uid, now).reasons}`); Task 7 does not repeat it. 

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/identity -v`
Expected: FAIL, `No module named 'platform_api.identity.provider'`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 11 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: sign-in to member, session cookie, terms gate, deletion request"
```

---

### Task 7: Support requests and limits

**Files:**
- Create: `tests/identity/test_http_member.py`
- Modify: `identity/models.py`, `store.py`, `public.py`, `http.py`

**Interfaces:**
- Produces: `identity.public.file_support_request(uid: str, kind: Literal["paid_not_recognised", "other"], note: str, now: datetime) -> str` and `list_support_requests() -> list[SupportRequest]`; `MemberStore` gains `add_support_request` and `support_requests`; route `POST /v1/me/support-requests` (uses `member_with_terms`).
- A note longer than 500 characters → 422. At most 5 requests per member per day → 429 `rate_limited` with `retry_after`. The limiter is `identity`'s `Runtime.limiter` (Task 6).
- The note is stored in `support_requests` and nowhere else. The event `membership.support.requested` carries `member_uid` and `kind` only. This event type is new: add it to the contracts page in this plan's pull request and to `docs/architecture/09-events-and-data-model.md` (the integrator makes both edits when asked in the hand-over).

- [ ] **Step 1: Write the failing tests**

```python
# tests/identity/test_http_member.py
import logging

from tests.identity.test_sessions import sign_in


def member(world, name="ed"):
    cookie = {"X-Member-Session": sign_in(world, name).json()["session"]["cookie"]}
    world.post("/v1/me/terms-acceptance", headers=cookie, json={"terms_version": "t1", "privacy_version": "p1"})
    return cookie


def test_a_note_is_stored_and_never_copied(world, idn, ent, caplog):
    cookie = member(world)
    with caplog.at_level(logging.DEBUG):
        r = world.post("/v1/me/support-requests", headers=cookie, json={"kind": "paid_not_recognised", "note": "I pay with another address"})
    assert r.status_code == 200 and r.json()["id"]
    assert [s.note for s in idn.members.support_requests()] == ["I pay with another address"]
    assert "another address" not in caplog.text
    [event] = [e for e in ent.bus.published if e.type.endswith("membership.support.requested")]
    assert event.data == {"member_uid": "u-ed", "kind": "paid_not_recognised"}


def test_a_long_note_and_an_unknown_kind_are_refused(world):
    cookie = member(world)
    assert world.post("/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "x" * 501}).status_code == 422
    assert world.post("/v1/me/support-requests", headers=cookie, json={"kind": "refund", "note": "x"}).status_code == 422


def test_the_sixth_request_in_a_day_is_limited(world):
    cookie = member(world)
    codes = [world.post("/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    last = world.post("/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}).json()
    assert last["error"]["code"] == "rate_limited" and last["error"]["retry_after"] > 0


def test_the_request_needs_accepted_terms(world):
    cookie = {"X-Member-Session": sign_in(world, "ed").json()["session"]["cookie"]}
    assert world.post("/v1/me/support-requests", headers=cookie, json={"kind": "other", "note": "n"}).status_code == 409
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/identity/test_http_member.py -v`
Expected: FAIL with 404 for the route.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 4 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: support requests, stored once, limited per member"
```

---

### Task 8: The owner's routes and `platform-cli`

**Files:**
- Create: `admin/models.py`, `admin/client.py`, `tests/admin/__init__.py`, `tests/admin/test_admin.py`, `tests/admin/test_cli_client.py`
- Modify: `admin/public.py`, `admin/http.py`, `shared/auth.py`, `cli.py`

**Interfaces:**
- **The owner's token is verified inside the service**, signature included. Cloud Run's own check is not enough here: any caller allowed to invoke the service (the website's account, for one) could otherwise present a token it wrote itself. `Deps` gains `verify_owner: Callable[[str], str] | None` (token → the Google account id in the claim `sub`; raises `NotAuthorised`), and `create_app` puts it on `app.state`. `None` refuses every admin request. The real one, `shared/auth.py: google_account_from_token(token) -> str`, calls `google.oauth2.id_token.verify_token(token, google.auth.transport.requests.Request())` (signature and expiry against Google's published keys), then requires the issuer `https://accounts.google.com` and `email_verified` true, and returns `sub`; `main.py` wires it. The audience is not checked: a token from `gcloud auth print-identity-token` for a person's account carries gcloud's own audience. The account list is the gate.
- `admin.public.owner`: the FastAPI dependency. It reads `Authorization: Bearer`, calls `request.app.state.verify_owner`, and accepts only an id in `request.app.state.settings.owner_accounts`. An empty list allows nobody.
- Consumes, and nothing else from the other modules: `entitlements.public` (`contact_id_for`, `upsert_contact`, `contact_view`, `grant`, `revoke`, `put_campaigns`, `list_campaigns`, `campaign_state` re-exported, `launch_config`, `update_launch_config`, `write_audit`) and `identity.public` (`list_support_requests`, `member_count`).
- `admin/http.py`: the dependency `owner` on the whole router (missing header or refused → 403 `forbidden`; the response does not say which). Every route, reads included, writes an audit entry with `actor = "owner:<account id>"`. The `subject` is the entitlement or contact id when the call is about one, and the fixed word `admin` for reads of lists and for configuration writes (campaigns, launch). Routes, as on the contracts page:

| Route | Calls |
| --- | --- |
| `POST /v1/admin/contacts/search` `{email}` | `contact_id_for`; returns `{contact: null}` or `{contact: {contact_id, channels, has_member, entitlements: [Reason + entitlement_id], audit: [AuditEntry]}}`. No address in the response |
| `POST /v1/admin/entitlements` `{email, grant, months` or `valid_until, reason}` | `upsert_contact`, then `grant`; exactly one of `months` and `valid_until`; → `{entitlement_id}` |
| `POST /v1/admin/entitlements/{id}/revoke` `{reason}` | `revoke`; unknown id → 404; not a grant → 422 |
| `PUT /v1/admin/campaigns` `{campaigns: [...]}` | validates every campaign (exactly one default; unique slugs; policy fields consistent), then `put_campaigns`; counts of an existing slug are kept; → `{written}` |
| `PUT /v1/admin/launch` (any subset of the three switches, the two required versions, `reconcile_max_age_seconds`, `substack_account_url`) | → the stored config |
| `GET /v1/admin/launch/report` | → `{campaigns: [{slug, state, counts}], members: <n>}`; promotions are added by the Commerce lane |
| `GET /v1/admin/support-requests` | → `{requests: [{id, member_uid, kind, note, created_at}]}` |

  `PUT /v1/admin/promotions` and `POST /v1/admin/library/publish` belong to the Commerce and Library lanes' routers under the same `owner` dependency, which they import from `admin.public`.
- `admin/client.py`: `class AdminClient` with `__init__(self, base_url: str, token: Callable[[], str], http: httpx.Client | None = None)` and one method per route. It sends `Authorization: Bearer <token>`; a non-2xx answer raises `AdminError(status, code, message)`.
- `cli.py` gains, beside `job`: `contact show --email-stdin`, `grant create --email-stdin --grant --months|--until --reason` (the address is read from standard input, one line, so it never appears in the process list or the shell history), `grant revoke --id --reason`, `campaign apply --file`, `launch set [--join-open true|false] [--library-open …] [--promotions-open …] [--terms-version …] [--privacy-version …] [--substack-account-url …]`, `launch report`, `support list`. `cli.admin_client() -> AdminClient` builds the client (tests replace it): the base address comes from `PLATFORM_API_URL` and the token from `gcloud auth print-identity-token` (no `--audiences`: that flag is for service accounts), run as a subprocess with a fixed argument list, never through a shell. Output is plain lines of the form `key: value`; no command prints an address except the one the owner typed. `stripe reconcile`, `roster import` and `promo apply` are added by the Commerce lane.
- `httpx` moves from the dev group to the runtime dependencies in `pyproject.toml`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/admin/test_admin.py
import base64
import json
import logging

import pytest
from fastapi.testclient import TestClient

from platform_api.app import Deps, create_app
from platform_api.settings import Settings
from tests.entitlements.test_campaigns import campaign
from tests.fixtures.people import EMAIL


def token(sub):
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    return f"{part({'alg': 'none'})}.{part({'sub': sub, 'email_verified': True})}.x"


def sub_of(tok):                       # stands in for Google's signature check
    from platform_api.shared.auth import NotAuthorised
    try:
        payload = tok.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]
    except Exception as exc:
        raise NotAuthorised("invalid") from exc


@pytest.fixture
def admin(idn, ent):
    client = TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=sub_of)))
    client.headers["Authorization"] = f"Bearer {token('acc-1')}"
    return client


def test_only_a_listed_account_gets_in(admin):
    for headers in ({"Authorization": f"Bearer {token('acc-2')}"}, {"Authorization": "Bearer junk"}, {"Authorization": ""}):
        r = admin.get("/v1/admin/launch/report", headers=headers)
        assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert admin.get("/v1/admin/launch/report").status_code == 200


def test_without_a_verifier_nobody_gets_in(idn, ent):
    client = TestClient(create_app(Settings(owner_accounts=["acc-1"])))
    assert client.get("/v1/admin/launch/report", headers={"Authorization": f"Bearer {token('acc-1')}"}).status_code == 403


def test_the_owner_list_reads_a_comma_separated_variable(monkeypatch):
    monkeypatch.setenv("PLATFORM_OWNER_ACCOUNTS", "acc-1, acc-2")
    assert Settings().owner_accounts == ["acc-1", "acc-2"]


def test_an_empty_owner_list_allows_nobody(idn, ent):
    client = TestClient(create_app(Settings(owner_accounts=[]), Deps(verify_owner=sub_of)))
    assert client.get("/v1/admin/launch/report", headers={"Authorization": f"Bearer {token('acc-1')}"}).status_code == 403


def test_grant_search_and_revoke_by_hand(admin, ent, caplog):
    with caplog.at_level(logging.DEBUG):
        made = admin.post("/v1/admin/entitlements", json={"email": EMAIL["di"], "grant": "tier:paid", "months": 6, "reason": "comp reader"})
        found = admin.post("/v1/admin/contacts/search", json={"email": " DI@example.org"}).json()["contact"]
    eid = made.json()["entitlement_id"]
    assert [e["entitlement_id"] for e in found["entitlements"]] == [eid] and found["has_member"] is False
    assert "@" not in json.dumps(found) and "@" not in caplog.text
    assert admin.post(f"/v1/admin/entitlements/{eid}/revoke", json={"reason": "mistake"}).status_code == 200
    assert admin.post("/v1/admin/entitlements/nope/revoke", json={"reason": "x"}).status_code == 404
    assert admin.post("/v1/admin/contacts/search", json={"email": EMAIL["bo"]}).json() == {"contact": None}


def test_a_grant_needs_exactly_one_end_and_a_reason(admin):
    base = {"email": EMAIL["di"], "grant": "tier:paid"}
    for extra in ({"reason": "r"}, {"months": 6, "valid_until": "2027-01-01T00:00:00Z", "reason": "r"}, {"months": 6, "reason": ""}):
        assert admin.post("/v1/admin/entitlements", json={**base, **extra}).status_code == 422


def test_every_call_is_audited_reads_included(admin, ent):
    admin.get("/v1/admin/support-requests")
    admin.put("/v1/admin/launch", json={"join_open": True})
    actions = [(a.actor, a.action) for a in ent.store.audit_for("admin")]
    assert actions == [("owner:acc-1", "admin.read"), ("owner:acc-1", "launch.switched")]


def test_campaigns_are_validated_and_counts_survive_a_rewrite(admin, ent):
    one = campaign().model_dump(mode="json")
    default = campaign("members", audience="public", grant=None, is_default=True).model_dump(mode="json")
    assert admin.put("/v1/admin/campaigns", json={"campaigns": [one]}).status_code == 422          # no default
    assert admin.put("/v1/admin/campaigns", json={"campaigns": [one, one, default]}).status_code == 422
    assert admin.put("/v1/admin/campaigns", json={"campaigns": [one, default]}).json() == {"written": 2}
    ent.store.add_to_campaign_count("founding", "arrivals")
    admin.put("/v1/admin/campaigns", json={"campaigns": [one, default]})
    assert ent.store.get_campaign("founding").counts["arrivals"] == 1


def test_launch_switches_take_a_subset_and_report_counts(admin):
    assert admin.put("/v1/admin/launch", json={"join_open": True, "required_terms_version": "2026-11-23"}).json()["join_open"] is True
    stored = admin.put("/v1/admin/launch", json={"library_open": True}).json()
    assert (stored["join_open"], stored["library_open"], stored["required_terms_version"]) == (True, True, "2026-11-23")
    assert admin.put("/v1/admin/launch", json={"join_open": "maybe"}).status_code == 422
```

```python
# tests/admin/test_cli_client.py
import httpx
import pytest

from platform_api import cli
from platform_api.admin.client import AdminClient, AdminError


def client(handler):
    return AdminClient("https://api.example.org", lambda: "tok", httpx.Client(transport=httpx.MockTransport(handler)))


def test_the_client_sends_the_token_and_puts_the_address_in_the_body():
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), auth=request.headers["authorization"], body=request.content.decode())
        return httpx.Response(200, json={"contact": None})

    assert client(handler).contact_show("ana@example.org") is None
    assert seen["auth"] == "Bearer tok" and "@" not in seen["url"] and "ana@example.org" in seen["body"]


def test_an_error_body_becomes_an_admin_error():
    with pytest.raises(AdminError) as err:
        client(lambda r: httpx.Response(403, json={"error": {"code": "forbidden", "message": "Not allowed.", "retry_after": None}})).launch_report()
    assert (err.value.status, err.value.code) == (403, "forbidden")


def test_launch_set_sends_only_what_was_typed(monkeypatch, capsys):
    sent = []
    monkeypatch.setattr(cli, "admin_client", lambda: client(lambda r: sent.append(r.content.decode()) or httpx.Response(200, json={"join_open": True, "library_open": False, "promotions_open": False})))
    assert cli.main(["launch", "set", "--join-open", "true"]) == 0
    assert sent == ['{"join_open":true}'] and "join_open: True" in capsys.readouterr().out


def test_a_refused_command_exits_non_zero_with_plain_words(monkeypatch, capsys):
    monkeypatch.setattr(cli, "admin_client", lambda: client(lambda r: httpx.Response(403, json={"error": {"code": "forbidden", "message": "Not allowed.", "retry_after": None}})))
    assert cli.main(["launch", "report"]) == 1 and "Not allowed." in capsys.readouterr().err
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/admin -v`
Expected: FAIL, 404 for the admin routes and `No module named 'platform_api.admin.client'`.

- [ ] **Step 3: Implement**

`campaign apply --file` reads YAML with `yaml.safe_load`, takes the key `campaigns`, and sends it; validation is the server's.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 13 new tests pass (9 and 4); `tests/test_module_registration.py` still passes.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: owner routes behind the account list, audited; platform-cli as their client"
```

---

### Task 9: The cloud versions of the ports

**Files:**
- Create: `adapters/__init__.py`, `adapters/firestore_entitlements.py`, `adapters/firestore_members.py`, `adapters/firestore_ratelimit.py`, `adapters/kms.py`, `adapters/firebase.py`; `tests/integration/test_firestore_stores.py`, `tests/test_adapters_unit.py`
- Modify: `main.py`, `cli.py` (jobs get the same runtimes), `.importlinter` (the `adapters` package may import every module's ports; no feature module imports `adapters`)

**Interfaces:**
- `FirestoreEntitlementStore(client)`, `FirestoreMemberStore(client)`, `FirestoreRateLimiter(client)`: the ports of Tasks 1, 5, 6 and 7 on the collections of 09 §2 and contracts §4 (`contacts`, `entitlements`, `audit_log`, `campaigns`, `config/launch`, `members`, `support_requests`, and the new `rate_limits`, which the integrator adds to 09). `write` and `create_if_absent` run in a Firestore transaction. `add_to_campaign_count` uses `Increment`.
- `KmsContactKey(client, key_version_name)`: `mac` calls `mac_sign(request={"name": …, "data": …, "data_crc32c": …})` and checks the response's `name` and CRC32C; `version` is the last path segment.
- `FirebaseIdentityProvider(app)`: `verify_id_token(check_revoked=True)`, `create_session_cookie`, `verify_session_cookie(check_revoked=True)`, `revoke_refresh_tokens`. It calls these as `firebase_admin.auth.<function>` through the module (so a test can replace them). Every `firebase_admin` error, and `ValueError`, becomes `InvalidToken` with a message that holds no token and no address.
- `main.py` builds the three runtimes lazily (no client is created at import; `/health` works without credentials) and calls `set_runtime` for `entitlements` and `identity`. A missing `PLATFORM_CONTACT_KEY` outside `local` stops the service at start with a message that names the setting; in `local`, `LocalContactKey` and the in-memory stores are used.
- **Lifetimes (added on 2026-11-23, from the privacy notice):** the Firestore stores write `expires_at` on every `support_requests` document (created + 365 days), every `audit_log` entry (at + 730 days) and every `rate_limits` counter (window end + 2 days). The Infra lane creates the time-to-live policies on that field. One integration test per collection asserts the field and its value.
- Firestore indexes the queries need are listed in the hand-over for the Infra lane (which owns Terraform): `entitlements` by `contact_id`, by `member_uid`, by `source`; `contacts` by `channels.platform.member_uid`.

- [ ] **Step 1: Write the failing tests**

`tests/integration/test_firestore_stores.py` (marked `integration`, runs against the emulator as the existing integration test does): run the **same assertions** as five in-memory tests by parametrising a store factory: `test_upsert_keeps_the_first_address_and_merges_channels`, `test_first_sign_in_claims_what_was_waiting`, `test_first_run_creates_and_second_run_changes_nothing`, `test_applying_twice_creates_one_grant_and_only_for_a_member`, `test_the_sixth_request_in_a_day_is_limited`; plus `test_two_writers_create_one_grant`: two threads call `create_if_absent` with the same record; exactly one returns `True` and one document exists.

```python
# tests/test_adapters_unit.py
import pytest

from platform_api.adapters.firebase import FirebaseIdentityProvider
from platform_api.adapters.kms import KmsContactKey
from platform_api.identity.provider import InvalidToken


class FakeKms:
    def __init__(self, name=None, crc_ok=True):
        self.name, self.crc_ok = name, crc_ok

    def mac_sign(self, request):
        import google_crc32c
        mac = b"m" * 32
        crc = google_crc32c.value(mac) if self.crc_ok else 1
        return type("R", (), {"name": self.name or request["name"], "mac": mac, "mac_crc32c": crc, "verified_data_crc32c": True})()


NAME = "projects/p/locations/l/keyRings/platform/cryptoKeys/contact-id/cryptoKeyVersions/1"


def test_the_key_reports_its_version_and_checks_the_answer():
    assert KmsContactKey(FakeKms(), NAME).version == "1" and KmsContactKey(FakeKms(), NAME).mac(b"x") == b"m" * 32
    for broken in (FakeKms(name="other"), FakeKms(crc_ok=False)):
        with pytest.raises(RuntimeError, match="contact key"):
            KmsContactKey(broken, NAME).mac(b"x")


def test_a_provider_error_becomes_invalid_token_without_the_token(monkeypatch):
    import firebase_admin.auth as fa

    def boom(*a, **k):
        raise fa.InvalidIdTokenError("bad token eyJhbGciOi for ana@example.org")

    monkeypatch.setattr(fa, "verify_id_token", boom)
    with pytest.raises(InvalidToken) as err:
        FirebaseIdentityProvider(app=None).verify_id_token("eyJhbGciOi")
    assert "eyJ" not in str(err.value) and "@" not in str(err.value)


def test_importing_main_creates_no_client(monkeypatch, restore_root_logger):
    monkeypatch.setenv("PLATFORM_ENV", "local")
    import importlib

    import platform_api.main as main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    assert TestClient(main.app).get("/health").status_code == 200
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/test_adapters_unit.py -v`
Expected: FAIL, `No module named 'platform_api.adapters'`.

- [ ] **Step 3: Implement, and wire `main.py` and the jobs**

- [ ] **Step 4: See them pass**

Run the check command, then the integration tests as CI does (`FIRESTORE_EMULATOR_HOST=localhost:8085 uv run pytest -m integration`). Expected: 3 new unit tests and 6 new integration tests pass; `lint-imports` reports the contracts kept.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: Firestore, Cloud KMS and Identity Platform behind the ports"
```

---

### Task 10 (task card C8, added on 2026-11-23): deleting a member on request

The privacy notice promises deletion within 30 days of a request. After Task 9, in its own pull request:

- `identity.public.pending_deletions() -> list[MemberRef]` and `delete_member(uid: str, actor: str, now: datetime) -> None`. `delete_member` refuses (`ValueError`) a member whose status is not `deletion_requested`. It removes, in this order: the member's entitlements (through a new `entitlements.public.forget_contact(contact_id, actor, now)`, which deletes the contact's entitlements and the contact record, and writes one audit entry `contact.forgotten` whose subject is the contact id); the member's support requests; the member record; and the sign-in account at the identity provider (`IdentityProvider.delete_user(uid)`, added to the port and its fake). A second call for the same uid does nothing and raises nothing.
- Routes under the `owner` dependency: `GET /v1/admin/deletions` → `{pending: [{uid, requested_at}]}` and `POST /v1/admin/members/{uid}/delete` → `{}` (404 for an unknown uid, 422 when the member did not request deletion). CLI: `platform-cli member deletions` and `platform-cli member delete --uid <uid>`.
- Tests, in `tests/identity/test_deletion.py`: after a request and a delete, the contact, the entitlements, the member and the support requests are gone, the provider's account is deleted, sign-in with the same address creates a **new** free member, and the audit trail holds one `contact.forgotten` entry with no address; a member who did not ask cannot be deleted; a second delete is harmless; a download record or audit entry of the deleted member holds no address (it never did) and is left to expire. Five tests.
- Commit: `platform-api: delete a member on request, by the owner's command`.

**Added on 2026-11-23, after the owner's answers to the two questions of the task's pull request (1a, 2a).** The deletion stays as built: nothing marks a forgotten contact, and the privacy notice now says that a continuing Substack subscription is found again. Two more owner commands complete a request made in writing. Same pull request, tests first:

- `identity.public.request_deletion_by_owner(uid: str, actor: str, now: datetime) -> None`: raises `LookupError` for an unknown uid; otherwise calls `request_deletion(uid, now)` and writes one audit entry `member.deletion_requested` with `actor` and the uid as subject. A second call keeps the first `deletion_requested_at` and writes no second entry.
- `entitlements.public.forget_unowned_contact(email: str, actor: str, now: datetime) -> bool`: derives the contact id with `contact_id_for`; returns `False` when no contact exists; raises `MemberExists` (new, exported) when `platform.member_uid` is set; otherwise calls `forget_contact` and returns `True`. The address is used for the id only: it reaches no log line, audit entry, event or response.
- `ContactView.member_uid: str | None`, filled by `contact_view`. `has_member` stays.
- Routes under the `owner` dependency, each with its line in `AUDIT_ACTIONS`: `POST /v1/admin/members/{uid}/deletion-request` → `{status: "deletion_requested"}` (404 unknown uid; action `member.deletion_requested`) and `POST /v1/admin/contacts/forget` with `{email}` → `{forgotten: bool}` (409 `member_exists`; action `contact.forgotten`; the audit subject is the contact id, never the address).
- CLI: `platform-cli member request-deletion --uid <uid>` and `platform-cli contact forget --email-stdin`. `contact forget` reads the address the way `contact show` does, prints `forgotten` or `no such contact`, and then the line `A reader who still pays through Substack is found again by the next reconcile.` `contact show` prints `member_uid` when there is one.
- Tests, in `tests/identity/test_deletion.py` and `tests/admin/`: a member who never pressed the button is marked by the owner, loses their sessions, and can then be deleted, with one `member.deletion_requested` entry naming the owner; an unknown uid answers 404; marking twice keeps the first time; a contact with no member is forgotten with its entitlements and one `contact.forgotten` entry; an address with no contact answers `forgotten: false` and changes nothing; a contact a member owns answers 409 and is untouched; no response, log line or audit entry of either route holds the address; a forgotten contact whose source still reports a live subscription is created again by the next `apply_plan`, with no member (this pins decision 1a). Eight tests.
- Commit: `platform-api: complete a deletion asked for in writing`.

---

## Exit test for this plan

1. The check command and the integration tests pass in CI on the branch.
2. With the in-memory runtimes, the journey of each fixture person gives the outcome of contracts §8 (the tests of Tasks 5 and 6 are that journey).
3. A search of the lane's diff finds no address outside `example.org`, no `print` of a token, and no `datetime.now()` outside `shared/clock.py`.
4. The hand-over lists: the two signatures that gained `now`; the new event type; the Firestore indexes for Infra; and the three settings Infra must set on the service (`PLATFORM_CONTACT_KEY`, `PLATFORM_OWNER_ACCOUNTS`, `PLATFORM_SESSION_TTL_DAYS`).
