# Stage 1 · Slice 0: Platform Skeleton and Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Lanes (added 2026-11-20):** tasks 1 to 5 are built by lane **L1 Core**, tasks 6 to 8 by lane **L3 Infra**, task 9 by the **integrator** ([swarm build plan](../../plans/stage-1-swarm-build-plan.md)). Each lane branches from `integration/stage-1` and opens its pull requests against it. Task 6 builds and tests the image of the service, so the Infra lane starts it only after Core's tasks 1 to 5 are merged into `integration/stage-1`; until then it works on tasks 7 and 8 and on its second plan. `services/platform-api/.dockerignore` belongs to the Infra lane together with the `Dockerfile`. Interfaces shared with other lanes are on the [contracts page](../../contracts/stage-1-launch.md).

**Goal:** A private `platform-api` and a public `platform-hooks` run in a new dev project from one image, exchange CloudEvents over Pub/Sub exactly-once-in-effect, and enforce module boundaries, so every later Stage 1 slice only adds business code.

**Architecture:** One Python package, `platform_api`, started in one of two HTTP modes (`api`, `hooks`) or as a job through `platform-cli`. Feature modules are empty packages with a `public.py`; shared code holds the event envelope, the bus port, the inbox and the Pub/Sub push receiver. Infrastructure is Terraform with one root per environment; applying it is the owner's step in Cloud Shell.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, uv, ruff, mypy, pytest, import-linter, google-cloud-firestore, google-cloud-pubsub, google-auth; Terraform (google ~> 6.10, cloudflare ~> 4.40); GitHub Actions with Workload Identity Federation.

**Spec:** `docs/architecture/01-system-overview.md` (§5, §6, §7), `docs/architecture/09-events-and-data-model.md` (§4), `docs/architecture/08-security-identities-and-org.md` (§3, §4), `docs/plans/stage-1-members-and-commerce.md` (S1.0), ADR 0006, ADR 0014, ADR 0015.

## Global Constraints

- Region for every regional resource: `asia-southeast1`.
- Projects: `audhd-neurobiology-prod` (exists), `audhd-neurobiology-dev` (new). Dev holds invented data only.
- No service account key files anywhere. GitHub authenticates by Workload Identity Federation.
- The repository is public: no real email, name, Stripe id or subscriber count in code, tests, fixtures or docs.
- CloudEvents 1.0. `type` starts with `org.audhdneurobiology.`; `source` is `//audhdneurobiology.org/platform-api`.
- Events and logs never contain an email address. `new_event` must reject any payload containing an email-shaped string.
- HTTP health path is `/health`. Do not use paths ending in `z` at the service root: Cloud Run reserves some of them.
- `platform-hooks` is public through `invoker_iam_disabled = true`; never bind `allUsers` (organisation policy forbids it, ADR 0005).
- Cloud Run minimum instances: 0.
- Feature modules (`identity`, `entitlements`, `commerce`, `library`, `content`, `admin`) import each other only through `<module>.public`. `shared` imports no feature module.
- Importing `platform_api.main` must not need cloud credentials: cloud clients are created on first use, not at import.
- Cloud Run checks the caller's identity token for private services and strips its signature before the request reaches the container. Code therefore reads claims from the token and never re-verifies the signature.
- Commits are authored as the owner's GitHub noreply identity (set in the session); never commit `terraform.tfvars`.
- The agent never runs `terraform apply`, never deploys to prod and never merges its own pull request.

## Review Focus

1. **The same event delivered twice** (Pub/Sub is at-least-once): the handler's effect happens once. Pinned in Task 4.
2. **A handler that fails**: the request returns 500 and the event is *not* recorded, so the retry runs the handler again. Pinned in Task 4.
3. **An email hidden deep in an event payload** (inside a list inside a dict): rejected before publishing. Pinned in Task 2.
4. **A valid Google token from the wrong service account** calling the push endpoint: 403. Pinned in Task 4.
5. **The public hooks service exposing internal routes**: in `hooks` mode `/v1/*` and `/internal/*` return 404, even when push dependencies are supplied. Pinned in Tasks 1 and 4.

---

## File Structure

```
services/platform-api/
├─ pyproject.toml                  dependencies, scripts (platform-cli), tool config
├─ .importlinter                   module boundary contracts
├─ Dockerfile
├─ src/platform_api/
│  ├─ settings.py                  Settings
│  ├─ app.py                       create_app(settings, deps) -> FastAPI
│  ├─ main.py                      ASGI entry for uvicorn
│  ├─ cli.py                       platform-cli job <name>
│  ├─ shared/
│  │  ├─ logging.py                JSON logs, email redaction
│  │  ├─ events.py                 DomainEvent, new_event, PersonalDataInEvent
│  │  ├─ bus.py                    EventBus, InMemoryBus, PubSubBus
│  │  ├─ inbox.py                  Inbox, InMemoryInbox, FirestoreInbox
│  │  ├─ handlers.py               HandlerRegistry
│  │  ├─ auth.py                   push_identity_from_token, PushIdentity
│  │  └─ pubsub_push.py            build_push_router
│  ├─ identity/ entitlements/ commerce/ library/ content/ admin/
│  │  └─ __init__.py, public.py    empty for now
│  └─ jobs/selfcheck.py            publishes platform.selfcheck.ran
└─ tests/
   ├─ conftest.py
   ├─ test_app_modes.py  test_events.py  test_bus.py  test_inbox.py
   ├─ test_pubsub_push.py  test_boundaries.py  test_selfcheck.py
   └─ integration/test_firestore_inbox.py

infra/terraform/
├─ modules/web_service/            (exists, unchanged)
├─ modules/platform_service/       one Cloud Run service from the platform image
├─ modules/event_bus/              topics, dead-letter topics, push subscriptions
├─ envs/prod/                      the current root, moved; same state
└─ envs/dev/                       new root, new state bucket

.github/workflows/platform-api.yml
ops/scripts/20-stage1-foundations.sh
ops/scripts/smoke-platform.sh
docs/runbooks/stage-1-foundations.md
CLAUDE.md
```

---

### Task 1: Service skeleton with two HTTP modes

**Files:**
- Create: `services/platform-api/pyproject.toml`, `src/platform_api/__init__.py`, `settings.py`, `app.py`, `main.py`, `shared/__init__.py`, `shared/logging.py`
- Test: `services/platform-api/tests/conftest.py`, `tests/test_app_modes.py`

**Interfaces:**
- Produces: `Settings` (fields below); `create_app(settings: Settings, deps: Deps | None = None) -> FastAPI`; `Deps` dataclass with `bus: EventBus | None`, `inbox: Inbox | None`, `registry: HandlerRegistry | None`, `verify_push: Callable[[str], PushIdentity] | None` (types arrive in Tasks 2 to 4; declare them with `TYPE_CHECKING` imports).

`Settings` fields, all read from environment variables with prefix `PLATFORM_`:

| Field | Type | Default |
| --- | --- | --- |
| `app_mode` | `Literal["api", "hooks"]` | `"api"` |
| `env` | `Literal["local", "dev", "prod"]` | `"local"` |
| `gcp_project` | `str` | `"local"` |
| `service_name` | `str` | `"platform-api"` |
| `events_topic` | `str` | `"platform.events"` |
| `inbound_topic` | `str` | `"inbound.webhooks"` |
| `push_audience` | `str` | `""` |
| `push_service_account` | `str` | `""` |

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app_modes.py
from fastapi.testclient import TestClient
from platform_api.app import create_app
from platform_api.settings import Settings


def client(mode: str) -> TestClient:
    return TestClient(create_app(Settings(app_mode=mode)))


def test_health_reports_mode():
    r = client("api").get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "platform-api", "mode": "api", "env": "local"}


def test_api_mode_serves_ping_and_no_hooks():
    c = client("api")
    assert c.get("/v1/ping").json() == {"pong": True}
    assert c.post("/hooks/stripe").status_code == 404


def test_hooks_mode_exposes_no_internal_or_api_routes():
    c = client("hooks")
    assert c.get("/health").status_code == 200
    assert c.get("/v1/ping").status_code == 404
    assert c.post("/internal/pubsub/platform-events").status_code == 404


def test_docs_are_off_outside_local():
    c = TestClient(create_app(Settings(env="prod")))
    assert c.get("/docs").status_code == 404
    assert c.get("/openapi.json").status_code == 404
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd services/platform-api && uv run pytest tests/test_app_modes.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'platform_api'`

- [ ] **Step 3: Write `pyproject.toml`**

Project name `platform-api`, `requires-python = ">=3.12,<3.13"`, src layout with a `[build-system]` table (`hatchling`, `packages = ["src/platform_api"]`; without it uv does not install the package and the script entry does not exist), script `platform-cli = "platform_api.cli:main"`. Runtime dependencies: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`, `google-cloud-firestore`, `google-cloud-pubsub`, `google-auth`, `requests`. Also add the launch track's runtime dependencies now, so that no other lane edits this file in Wave 2: `stripe`, `firebase-admin`, `google-cloud-kms`, `google-cloud-storage`, `google-cloud-run`, `google-cloud-secret-manager`, `pyyaml`. Dev group: `pytest`, `httpx`, `ruff`, `mypy`, `import-linter`, `types-PyYAML`. Configure ruff (line length 100, rules `E,F,I,UP,B,S`, with per-file ignores `S101` and `E501` for `tests/**`), mypy `strict = true` for `platform_api`, pytest marker `integration`. Format with `ruff format` and let `ruff check --fix` order imports before committing; the test code in this plan is written for readability, not to the formatter's line breaks. Run `uv lock` and commit `uv.lock`; the image build installs from it.

- [ ] **Step 4: Implement `Settings`, `create_app` and `shared/logging.py`**

`create_app` mounts `/health` always; `/v1/ping` only in `api` mode; the push router (Task 4) only in `api` mode and only when `deps` carries an inbox; nothing else in `hooks` mode. OpenAPI and docs URLs are `None` unless `env == "local"`. `shared/logging.py` exposes `configure_logging(service: str) -> None`, which emits one JSON object per line with `severity`, `message`, `service` and replaces any email-shaped substring in the message with `[email]`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_app_modes.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: service skeleton with api and hooks modes"
```

---

### Task 2: Event envelope that refuses personal data

**Files:**
- Create: `src/platform_api/shared/events.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Produces:
  - `EVENT_PREFIX = "org.audhdneurobiology."`, `EVENT_SOURCE = "//audhdneurobiology.org/platform-api"`
  - `class DomainEvent(BaseModel)`: `specversion: Literal["1.0"]`, `id: str`, `type: str`, `source: str`, `subject: str`, `time: datetime`, `datacontenttype: Literal["application/json"]`, `data: dict[str, Any]`
  - `new_event(type_suffix: str, subject: str, data: dict[str, Any], *, event_id: str | None = None, now: datetime | None = None) -> DomainEvent`
  - `class PersonalDataInEvent(ValueError)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_events.py
from datetime import UTC, datetime
import pytest
from platform_api.shared.events import EVENT_SOURCE, PersonalDataInEvent, new_event

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def test_new_event_builds_a_cloudevent():
    e = new_event("membership.tier.changed", "c_0123", {"from": "paid", "to": "free"}, event_id="e1", now=NOW)
    assert e.model_dump(mode="json") == {
        "specversion": "1.0",
        "id": "e1",
        "type": "org.audhdneurobiology.membership.tier.changed",
        "source": EVENT_SOURCE,
        "subject": "c_0123",
        "time": "2026-11-16T12:00:00Z",
        "datacontenttype": "application/json",
        "data": {"from": "paid", "to": "free"},
    }


def test_event_id_defaults_to_a_fresh_uuid():
    a = new_event("x.y.happened", "s", {})
    b = new_event("x.y.happened", "s", {})
    assert a.id != b.id and len(a.id) == 32


@pytest.mark.parametrize(
    "subject,data",
    [
        ("someone@example.org", {}),
        ("c_1", {"email": "someone@example.org"}),
        ("c_1", {"items": [{"note": "write to Some.One+tag@Example.co.uk please"}]}),
    ],
)
def test_email_anywhere_in_the_event_is_rejected(subject, data):
    with pytest.raises(PersonalDataInEvent):
        new_event("x.y.happened", subject, data)


def test_type_suffix_must_not_repeat_the_prefix_or_be_empty():
    with pytest.raises(ValueError):
        new_event("org.audhdneurobiology.x.y.happened", "s", {})
    with pytest.raises(ValueError):
        new_event("", "s", {})
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_events.py -v`
Expected: FAIL, `ImportError` on `platform_api.shared.events`

- [ ] **Step 3: Implement `events.py`**

The email check walks `subject` and every string inside `data` (dict values, list items, nested to any depth) and matches `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`. `time` serialises as UTC with a `Z` suffix.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_events.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: CloudEvents envelope that rejects email addresses"
```

---

### Task 3: Bus port and inbox

**Files:**
- Create: `src/platform_api/shared/bus.py`, `src/platform_api/shared/inbox.py`
- Test: `tests/test_bus.py`, `tests/test_inbox.py`, `tests/integration/test_firestore_inbox.py`

**Interfaces:**
- Consumes: `DomainEvent` from Task 2.
- Produces:
  - `class EventBus(Protocol)`: `publish(self, event: DomainEvent) -> str` (message id)
  - `class InMemoryBus`: attribute `published: list[DomainEvent]`
  - `class PubSubBus`: `__init__(self, publisher: PublisherClient, project: str, topic: str)`. Message body is the event as JSON; attributes `ce-id`, `ce-type`, `ce-subject`.
  - `class Inbox(Protocol)`: `seen(self, event_id: str) -> bool`; `record(self, event_id: str, *, event_type: str, received_at: datetime) -> None` (calling it twice is not an error)
  - `class InMemoryInbox`, `class FirestoreInbox`: `__init__(self, client: firestore.Client, collection: str = "inbox")`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bus.py
import json
from platform_api.shared.bus import InMemoryBus, PubSubBus
from platform_api.shared.events import new_event


class FakeFuture:
    def result(self, timeout=None):
        return "m-1"


class FakePublisher:
    def __init__(self):
        self.calls = []

    def topic_path(self, project, topic):
        return f"projects/{project}/topics/{topic}"

    def publish(self, topic, data, **attrs):
        self.calls.append((topic, data, attrs))
        return FakeFuture()


def test_in_memory_bus_keeps_events():
    bus = InMemoryBus()
    e = new_event("x.y.happened", "s", {"n": 1})
    bus.publish(e)
    assert bus.published == [e]


def test_pubsub_bus_publishes_json_with_ce_attributes():
    pub = FakePublisher()
    e = new_event("x.y.happened", "s-1", {"n": 1}, event_id="e1")
    assert PubSubBus(pub, "proj", "platform.events").publish(e) == "m-1"
    topic, data, attrs = pub.calls[0]
    assert topic == "projects/proj/topics/platform.events"
    assert json.loads(data)["id"] == "e1"
    assert attrs == {"ce-id": "e1", "ce-type": "org.audhdneurobiology.x.y.happened", "ce-subject": "s-1"}
```

```python
# tests/test_inbox.py
from datetime import UTC, datetime
from platform_api.shared.inbox import InMemoryInbox

NOW = datetime(2026, 11, 16, tzinfo=UTC)


def test_inbox_remembers_and_tolerates_repeats():
    inbox = InMemoryInbox()
    assert inbox.seen("e1") is False
    inbox.record("e1", event_type="t", received_at=NOW)
    inbox.record("e1", event_type="t", received_at=NOW)
    assert inbox.seen("e1") is True
    assert inbox.seen("e2") is False
```

```python
# tests/integration/test_firestore_inbox.py   (needs FIRESTORE_EMULATOR_HOST)
import os
from datetime import UTC, datetime
import pytest
from google.cloud import firestore
from platform_api.shared.inbox import FirestoreInbox

pytestmark = pytest.mark.integration


@pytest.mark.skipif("FIRESTORE_EMULATOR_HOST" not in os.environ, reason="emulator not running")
def test_firestore_inbox_round_trip():
    inbox = FirestoreInbox(firestore.Client(project="test"), collection="inbox_test")
    now = datetime(2026, 11, 16, tzinfo=UTC)
    assert inbox.seen("e-int-1") is False
    inbox.record("e-int-1", event_type="t", received_at=now)
    inbox.record("e-int-1", event_type="t", received_at=now)
    assert inbox.seen("e-int-1") is True
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_bus.py tests/test_inbox.py -v`
Expected: FAIL, `ImportError`

- [ ] **Step 3: Implement `bus.py` and `inbox.py`**

`FirestoreInbox.record` uses `document(event_id).create(...)` and treats "already exists" as success. Document fields: `event_type`, `received_at`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_bus.py tests/test_inbox.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: event bus port and idempotency inbox"
```

---

### Task 4: Pub/Sub push receiver

**Files:**
- Create: `src/platform_api/shared/handlers.py`, `src/platform_api/shared/auth.py`, `src/platform_api/shared/pubsub_push.py`
- Modify: `src/platform_api/app.py` (mount the router in `api` mode)
- Test: `tests/test_pubsub_push.py`

**Interfaces:**
- Consumes: `DomainEvent`, `Inbox`, `Deps`, `create_app`.
- Produces:
  - `Handler = Callable[[DomainEvent], None]`
  - `class HandlerRegistry`: `register(self, type_suffix: str, handler: Handler) -> None`; `handlers_for(self, event_type: str) -> list[Handler]`
  - `@dataclass(frozen=True) class PushIdentity`: `email: str`
  - `class NotAuthorised(Exception)`
  - `push_identity_from_token(token: str, *, allowed_email: str) -> PushIdentity`: decodes the token's claims **without verifying the signature** (Cloud Run has already verified it and removed the signature; see Global Constraints) and raises `NotAuthorised("invalid")` if the token cannot be decoded or has no verified email, `NotAuthorised("wrong_identity")` if the email differs from `allowed_email`. The docstring must say why skipping verification is safe here and only here: the service is deployed with Cloud Run IAM required, which Terraform enforces.
  - `build_push_router(*, inbox: Inbox, registry: HandlerRegistry, verify: Callable[[str], PushIdentity]) -> APIRouter` serving `POST /internal/pubsub/platform-events`

Response rules for the endpoint:

| Situation | Status |
| --- | --- |
| No bearer token, or `verify` raises `NotAuthorised("invalid")` | 401 |
| Token valid but for another service account | 403 |
| Body is not a Pub/Sub push envelope, or the message is not a valid `DomainEvent` | 204, logged as an error (it can never succeed, so it must not be retried) |
| Event id already in the inbox | 204, no handler called |
| No handler registered for the type | 204, recorded |
| All handlers return | 204, recorded |
| Any handler raises | 500, **not** recorded |

To tell 401 from 403, `NotAuthorised` carries `reason: Literal["invalid", "wrong_identity"]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pubsub_push.py
import base64
import json
import pytest
from fastapi.testclient import TestClient
from platform_api.app import Deps, create_app
from platform_api.settings import Settings
from platform_api.shared.auth import NotAuthorised, PushIdentity
from platform_api.shared.events import new_event
from platform_api.shared.handlers import HandlerRegistry
from platform_api.shared.inbox import InMemoryInbox

URL = "/internal/pubsub/platform-events"
GOOD = {"Authorization": "Bearer good"}


def verify(token: str) -> PushIdentity:
    if token == "good":
        return PushIdentity(email="pubsub-push@test.iam.gserviceaccount.com")
    if token == "other-sa":
        raise NotAuthorised("wrong_identity")
    raise NotAuthorised("invalid")


def envelope(event) -> dict:
    data = base64.b64encode(event.model_dump_json().encode()).decode()
    return {"message": {"data": data, "messageId": "1"}, "subscription": "s"}


@pytest.fixture
def setup():
    calls: list[str] = []
    registry = HandlerRegistry()
    inbox = InMemoryInbox()
    app = create_app(Settings(), Deps(bus=None, inbox=inbox, registry=registry, verify_push=verify))
    return TestClient(app, raise_server_exceptions=False), registry, inbox, calls


def test_rejects_missing_and_invalid_tokens(setup):
    c, *_ = setup
    assert c.post(URL, json={}).status_code == 401
    assert c.post(URL, json={}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_rejects_a_valid_token_from_another_service_account(setup):
    c, *_ = setup
    assert c.post(URL, json={}, headers={"Authorization": "Bearer other-sa"}).status_code == 403


def test_duplicate_delivery_runs_the_handler_once(setup):
    c, registry, inbox, calls = setup
    registry.register("x.y.happened", lambda e: calls.append(e.id))
    body = envelope(new_event("x.y.happened", "s", {}, event_id="e1"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert calls == ["e1"]
    assert inbox.seen("e1")


def test_failing_handler_returns_500_and_is_retried(setup):
    c, registry, inbox, calls = setup
    attempts = {"n": 0}

    def flaky(e):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("boom")
        calls.append(e.id)

    registry.register("x.y.happened", flaky)
    body = envelope(new_event("x.y.happened", "s", {}, event_id="e2"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 500
    assert not inbox.seen("e2")
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert calls == ["e2"]


def test_unknown_type_is_recorded_and_acknowledged(setup):
    c, _, inbox, _ = setup
    body = envelope(new_event("nobody.listens.here", "s", {}, event_id="e3"))
    assert c.post(URL, json=body, headers=GOOD).status_code == 204
    assert inbox.seen("e3")


@pytest.mark.parametrize("body", [{}, {"message": {"data": "not-base64!"}}, {"message": {"data": base64.b64encode(b"{}").decode()}}])
def test_malformed_messages_are_acknowledged_not_retried(setup, body):
    c, *_ = setup
    assert c.post(URL, json=body, headers=GOOD).status_code == 204


def test_hooks_mode_never_mounts_the_receiver_even_with_dependencies():
    deps = Deps(bus=None, inbox=InMemoryInbox(), registry=HandlerRegistry(), verify_push=verify)
    c = TestClient(create_app(Settings(app_mode="hooks"), deps))
    assert c.post(URL, json={}, headers=GOOD).status_code == 404
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_pubsub_push.py -v`
Expected: FAIL, `ImportError`

- [ ] **Step 3: Implement `handlers.py`, `auth.py`, `pubsub_push.py`; mount the router in `create_app`**

In `main.py`, production wiring builds `Deps` lazily (clients are created on first use, so importing the module needs no credentials) with `PubSubBus`, `FirestoreInbox` and `verify=lambda t: push_identity_from_token(t, allowed_email=settings.push_service_account)`. Order inside the endpoint: authenticate, decode, `inbox.seen`, run handlers, `inbox.record`. The inbox is a shortcut: handlers added in later slices must themselves be safe to run twice, because one failing handler makes Pub/Sub redeliver the event to all of them.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v -m "not integration"`
Expected: all pass (22 tests)

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: authenticated, idempotent Pub/Sub push receiver"
```

---

### Task 5: Module boundaries and the self-check job

**Files:**
- Create: `src/platform_api/modules.py`; `src/platform_api/{identity,entitlements,commerce,library,content,admin}/__init__.py`, `public.py`, `http.py` and `jobs.py`; `services/platform-api/.importlinter`; `src/platform_api/cli.py`; `src/platform_api/jobs/__init__.py`, `jobs/selfcheck.py`
- Modify: `src/platform_api/app.py` (serve each module's routers)
- Test: `tests/test_boundaries.py`, `tests/test_selfcheck.py`, `tests/test_module_registration.py`

**Interfaces:**
- Consumes: `EventBus`, `new_event`.
- Produces:
  - `run_selfcheck(bus: EventBus) -> str`: publishes `platform.selfcheck.ran` with subject `platform-api` and data `{"check": "bus"}`, prints the event id on its own line, returns it
  - `platform-cli job <name>`: runs a job from the registry `JOBS: dict[str, Callable[[Settings], int]]`; unknown name exits with status 2 and lists the known names
  - Import contracts: (a) the six feature modules are independent of each other except for imports of `<module>.public`; (b) `platform_api.shared` imports none of them
  - `modules.FEATURE_MODULES: tuple[str, ...] = ("identity", "entitlements", "commerce", "library", "content", "admin")`
  - **Routes per module.** Each feature module's `http.py` exposes `router: fastapi.APIRouter` (served only in `api` mode) and `hooks_router: fastapi.APIRouter` (served only in `hooks` mode). Both are empty in this slice. `create_app` looks them up as `platform_api.<module>.http` **each time it is called** and includes them. Later lanes add routes to their own module's routers and never edit `app.py`.
  - **Jobs per module.** Each feature module's `jobs.py` exposes `JOBS: dict[str, Callable[[Settings], int]]`, empty in this slice. `cli.build_registry() -> dict[str, Callable[[Settings], int]]` merges `platform_api.jobs.JOBS` (the shared jobs, here `selfcheck`) with every module's `JOBS`; a name registered twice raises `cli.DuplicateJob`, whose message names both owners. `platform-cli job <name>` uses this registry.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_boundaries.py
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "src/platform_api/library/_probe_forbidden.py"


def lint() -> int:
    return subprocess.run(["lint-imports"], cwd=ROOT, capture_output=True).returncode


def test_skeleton_respects_boundaries():
    assert lint() == 0


def test_reaching_into_another_module_fails_the_lint():
    target = ROOT / "src/platform_api/entitlements/_probe_internal.py"   # never a real file
    target.touch()
    PROBE.write_text("from platform_api.entitlements import _probe_internal  # noqa: F401\n")
    try:
        assert lint() != 0
    finally:
        PROBE.unlink()
        target.unlink()


def test_public_interface_is_allowed():
    PROBE.write_text("from platform_api.entitlements import public  # noqa: F401\n")
    try:
        assert lint() == 0
    finally:
        PROBE.unlink()
```

```python
# tests/test_selfcheck.py
from platform_api.jobs.selfcheck import run_selfcheck
from platform_api.shared.bus import InMemoryBus


def test_selfcheck_publishes_one_event_and_prints_its_id(capsys):
    bus = InMemoryBus()
    event_id = run_selfcheck(bus)
    assert [e.type for e in bus.published] == ["org.audhdneurobiology.platform.selfcheck.ran"]
    assert bus.published[0].id == event_id
    assert capsys.readouterr().out.strip().splitlines()[-1] == event_id
```

```python
# tests/test_module_registration.py
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from platform_api import cli
from platform_api.app import create_app
from platform_api.settings import Settings


def _probe_router(path: str) -> APIRouter:
    router = APIRouter()

    @router.get(path)
    def probe() -> dict[str, bool]:
        return {"ok": True}

    return router


def test_a_module_route_is_served_in_api_mode_only(monkeypatch):
    from platform_api.library import http as library_http

    monkeypatch.setattr(library_http, "router", _probe_router("/v1/library/probe"))
    assert TestClient(create_app(Settings(app_mode="api"))).get("/v1/library/probe").json() == {"ok": True}
    assert TestClient(create_app(Settings(app_mode="hooks"))).get("/v1/library/probe").status_code == 404


def test_a_module_hook_route_is_served_in_hooks_mode_only(monkeypatch):
    from platform_api.commerce import http as commerce_http

    monkeypatch.setattr(commerce_http, "hooks_router", _probe_router("/hooks/probe"))
    assert TestClient(create_app(Settings(app_mode="hooks"))).get("/hooks/probe").json() == {"ok": True}
    assert TestClient(create_app(Settings(app_mode="api"))).get("/hooks/probe").status_code == 404


def test_a_job_registered_by_a_module_is_runnable(monkeypatch):
    from platform_api.commerce import jobs as commerce_jobs

    monkeypatch.setattr(commerce_jobs, "JOBS", {"probe-job": lambda settings: 7})
    assert cli.build_registry()["probe-job"](Settings()) == 7


def test_the_same_job_name_in_two_modules_is_refused(monkeypatch):
    from platform_api.commerce import jobs as commerce_jobs
    from platform_api.library import jobs as library_jobs

    monkeypatch.setattr(commerce_jobs, "JOBS", {"twin": lambda settings: 0})
    monkeypatch.setattr(library_jobs, "JOBS", {"twin": lambda settings: 0})
    with pytest.raises(cli.DuplicateJob) as err:
        cli.build_registry()
    assert "commerce" in str(err.value) and "library" in str(err.value)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_boundaries.py tests/test_selfcheck.py tests/test_module_registration.py -v`
Expected: FAIL (no `.importlinter`, no `jobs.selfcheck`, no `platform_api.library.http`)

- [ ] **Step 3: Create the module packages, `.importlinter`, `modules.py`, `cli.py`, `jobs/selfcheck.py`, and serve the module routers from `app.py`**

Two contracts in `.importlinter` with `root_package = platform_api`: an `independence` contract over the six feature modules that ignores imports whose target is a module's `public`, and a `forbidden` contract with `source_modules = platform_api.shared` and the six feature modules as `forbidden_modules`. The three boundary tests are the specification: adjust the ignore patterns until all three pass. A module's `http.py` and `jobs.py` are part of that module: they may import its own code and other modules' `public` only. `app.py` and `cli.py` sit outside the feature modules and import each module's `http` and `jobs` by name with `importlib.import_module`, at call time, so a test can replace a module's router or job table.

- [ ] **Step 4: Run all tests and the linters**

Run: `uv run pytest -v -m "not integration" && uv run ruff check . && uv run mypy src`
Expected: all pass, no lint or type errors

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "platform-api: enforced module boundaries and a bus self-check job"
```

---

### Task 6: Container image and CI

**Files:**
- Create: `services/platform-api/Dockerfile`, `services/platform-api/.dockerignore`, `.github/workflows/platform-api.yml`

**Interfaces:**
- Produces: image `<registry>/platform-api:<git sha>`; default command serves HTTP on `$PORT` (8080); the same image runs jobs with the command `platform-cli job <name>`.

- [ ] **Step 1: Write the Dockerfile**

Base `python:3.12-slim`; install with `uv sync --frozen --no-dev`; run as a non-root user; `CMD ["uvicorn", "platform_api.main:app", "--host", "0.0.0.0", "--port", "8080"]`. `PLATFORM_APP_MODE` selects the mode at run time.

- [ ] **Step 2: Build and smoke-test locally**

Run:
```bash
docker build -f services/platform-api/Dockerfile -t platform-api:local .
docker run --rm -d -p 8080:8080 -e PLATFORM_APP_MODE=hooks --name pa platform-api:local
curl -s localhost:8080/health; curl -s -o /dev/null -w "%{http_code}\n" localhost:8080/v1/ping; docker stop pa
```
Expected: `{"status":"ok","service":"platform-api","mode":"hooks","env":"local"}` then `404`

- [ ] **Step 3: Write `.github/workflows/platform-api.yml`**

Triggers: every pull request touching `services/platform-api/**` or the workflow file, whatever its target branch; pushes to `main` and to `integration/**` touching the same paths; tags `v*`.

| Job | When | Does |
| --- | --- | --- |
| `test` | always | `uv sync`, `ruff check`, `mypy src`, `lint-imports`, `pytest -m "not integration"`; then start the Firestore emulator in a step (GitHub service containers cannot take a command, so use `docker run -d -p 8085:8085 gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators gcloud emulators firestore start --host-port=0.0.0.0:8085`, wait until port 8085 answers) and run `pytest -m integration` with `FIRESTORE_EMULATOR_HOST=localhost:8085` |
| `deploy-dev` | push to `integration/stage-1` while the build runs in integration-branch mode (`docs/swarm/README.md`); the job's condition names that one branch, so the daily promotion to `main` does not deploy a second time; the condition also requires `vars.DEPLOY_DEV_ENABLED == 'true'`, a variable the owner sets on the GitHub environment `dev` at Gate 1 (before that, the environment has no variables of its own and `vars.*` would fall back to the repository-level values, which point at the prod project); after `test` | GitHub environment `dev`; authenticate with Workload Identity Federation; build and push the image; `gcloud run deploy platform-api` and `platform-hooks` with `--image`; `gcloud run jobs update platform-selfcheck --image` |
| `deploy-prod` | tag `v*`, after `test` | GitHub environment `production`; same steps against prod |

Read `GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOYER_SA`, `REGISTRY` from **environment-scoped** variables, so both environments use the same names. Deploy steps change only the image; all other service settings belong to Terraform.

- [ ] **Step 4: Verify the workflow file**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/platform-api.yml'))" && echo valid`
Expected: `valid`. The `test` job must pass on the pull request before review.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api/Dockerfile services/platform-api/.dockerignore .github/workflows/platform-api.yml
git commit -m "platform-api: container image and CI with emulator tests"
```

---

### Task 7: Terraform, one root per environment

**Files:**
- Move: `infra/terraform/{main,domain,monitoring,outputs,variables,versions}.tf` → `infra/terraform/envs/prod/`
- Create: `infra/terraform/modules/platform_service/{main,variables,outputs}.tf`, `infra/terraform/modules/event_bus/{main,variables,outputs}.tf`, `infra/terraform/envs/prod/platform.tf`, `infra/terraform/envs/prod/identities.tf`, `infra/terraform/envs/dev/{main,platform,identities,variables,versions,outputs}.tf`
- Modify: `.github/workflows/terraform.yml` (validate both roots), `ops/scripts/00-bootstrap.sh` and `10-domain.sh` (new path)

**Interfaces:**
- Produces Terraform outputs in each root: `platform_api_url`, `platform_hooks_url`, `artifact_registry`, `wif_provider`, `deployer_service_account`.
- `module "platform_service"` inputs: `name`, `project_id`, `region`, `image`, `service_account_email`, `public` (bool), `env` (map), `invokers` (list of service account emails). When `public` is true it sets `invoker_iam_disabled = true`; otherwise it grants `roles/run.invoker` to each of `invokers`. The image is ignored in `lifecycle`, as in `web_service`.
- `module "event_bus"` inputs: `project_id`, `push_endpoint_base`, `push_service_account_email`, `push_audience`. It creates the resources in the table below.

Resources per environment:

| Kind | Names |
| --- | --- |
| Service accounts | `platform-api`, `platform-hooks`, `job-selfcheck`, `pubsub-push` (each later job gets its own account in the slice that adds it) |
| Pub/Sub topics | `platform.events`, `platform.events.dlq`, `inbound.webhooks`, `inbound.webhooks.dlq` |
| Push subscriptions | `platform-events-to-api` → `<api url>/internal/pubsub/platform-events`; OIDC as `pubsub-push`; acknowledgement deadline 60 s; dead-letter after 5 attempts; retry back-off 10 s to 600 s; message retention 7 days. (`inbound-webhooks-to-api`, its own receiver route and the raw-event bucket are added in S1.3.) |
| Dead-letter handling | One pull subscription per dead-letter topic (`platform-events-dlq-hold`, `inbound-webhooks-dlq-hold`, retention 7 days) so nothing is discarded, and one alert policy per subscription on any undelivered message, notifying `alert_email` |
| Workload identity | Dev: provider restricted to this repository. Prod: the existing provider additionally maps `attribute.environment` and `attribute.ref`, and the prod `github-deployer` can be impersonated only when `attribute.environment == "production"` and the ref starts with `refs/tags/v` |
| Firestore | Database `(default)`, native mode, `asia-southeast1`, point-in-time recovery on; delete protection on in prod |
| Cloud Run services | `platform-api` (private; invokers `pubsub-push`, `web-runtime`; env `PLATFORM_APP_MODE=api`, `PLATFORM_ENV`, `PLATFORM_GCP_PROJECT`, `PLATFORM_PUSH_AUDIENCE`, `PLATFORM_PUSH_SERVICE_ACCOUNT`), `platform-hooks` (public; `PLATFORM_APP_MODE=hooks`) |
| Cloud Run job | `platform-selfcheck` running `platform-cli job selfcheck` as `job-selfcheck` |
| IAM | `platform-api`: `roles/datastore.user`, publisher on `platform.events`. `platform-hooks`: publisher on `inbound.webhooks` only. `job-selfcheck`: publisher on `platform.events` only. Pub/Sub service agent: publisher on both dead-letter topics, subscriber on the subscription. `github-deployer`: `roles/run.developer`, registry writer, `roles/iam.serviceAccountUser` on the three runtime accounts |
| Audit | Data access logs (`DATA_READ`, `DATA_WRITE`) for `datastore.googleapis.com` in prod |

The dev root also contains: enabled APIs, the Artifact Registry repository `platform`, the Workload Identity pool `github` and provider `github-oidc` restricted to this repository, `web-runtime` and `github-deployer` service accounts, and `module "web_dev"` with its domain mapping and DNS record for `dev.<domain>`. Task 8 removes those from prod, and prod is applied **before** dev so the two roots never both claim the `dev` host.

- [ ] **Step 1: Move the prod root without changing state**

```bash
mkdir -p infra/terraform/envs/prod && git mv infra/terraform/*.tf infra/terraform/envs/prod/
sed -i 's#"./modules/web_service"#"../../modules/web_service"#' infra/terraform/envs/prod/main.tf
```
The backend bucket and prefix stay the same, so the existing state is reused. Update the `cd` paths in `ops/scripts/00-bootstrap.sh` and `10-domain.sh` to `infra/terraform/envs/prod`.

- [ ] **Step 2: Write the two modules and `platform.tf` and `identities.tf` for prod**

`identities.tf` holds every service account and every IAM binding of the environment and nothing else: it is the permissions manifest described in `docs/architecture/08-security-identities-and-org.md`.

- [ ] **Step 3: Write the dev root**

Same files as prod, with `project_id = "audhd-neurobiology-dev"`, no delete protection, no budget resource (the budget is on the billing account, in prod), no Cloudflare apex records.

- [ ] **Step 4: Validate both roots in CI**

Change `.github/workflows/terraform.yml` to run `terraform fmt -check -recursive infra/terraform` and, for each of `envs/dev` and `envs/prod`, `terraform init -backend=false && terraform validate`.
Expected on the pull request: the Terraform workflow passes for both roots.

- [ ] **Step 5: Commit**

```bash
git add infra/terraform ops/scripts .github/workflows/terraform.yml
git commit -m "infra: one Terraform root per environment; platform services, bus and Firestore"
```

---

### Task 8: Foundations script, smoke test and runbook (hand-over to the owner)

**Files:**
- Create: `ops/scripts/20-stage1-foundations.sh`, `ops/scripts/smoke-platform.sh`, `docs/runbooks/stage-1-foundations.md`
- Modify: `infra/terraform/envs/prod/main.tf` and `domain.tf` (remove `module.web_dev` and the `dev` domain mapping), `.github/workflows/web.yml` (use GitHub environments `dev` and `production` with environment-scoped variables)

**Interfaces:**
- `20-stage1-foundations.sh` is safe to re-run and does, in order: (1) create the folder `audhd-neurobiology` under the organisation if absent and move the prod project into it after an explicit `y/N` prompt; (2) create `audhd-neurobiology-dev` in the folder and link billing; (3) create `gs://audhd-neurobiology-dev-tfstate` with versioning and public-access prevention; (4) `terraform init` and `terraform apply` in `envs/prod` first, showing the plan and the real prompt (no `| tail`): this removes `web-dev` and the `dev` host from prod and adds the platform resources; (5) the same in `envs/dev`, which creates the dev services and takes over the `dev` host; (6) build and push the first `platform-api` image to each registry and deploy both services and the job; (7) create GitHub environments `dev` and `production` and set `GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOYER_SA`, `RUNTIME_SA` and `REGISTRY` in each with `gh variable set --env`; (8) remind the owner to add herself as required reviewer on the `production` environment. Both applies need `TF_VAR_cloudflare_api_token`. `dev.<domain>` is unavailable between steps 4 and 5 and while its certificate is issued.
- `smoke-platform.sh <project>` does: (a) `curl` `platform-api` `/health` with an identity token, expect `"mode":"api"`; (b) `curl` `platform-hooks` `/health` with no token, expect `"mode":"hooks"`, and `/v1/ping`, expect 404; (c) `gcloud run jobs execute platform-selfcheck --wait`, read the event id from the job's last log line; (d) poll the Firestore REST API for `inbox/<event id>` for up to 60 seconds; (e) publish the same event a second time with `gcloud pubsub topics publish` and check in the service's logs that the second delivery was acknowledged as a duplicate and no handler ran; (f) print `SMOKE PASSED` or the first failing step and exit non-zero.

- [ ] **Step 1: Write the two scripts**

Follow the conventions of `00-bootstrap.sh`: `set -euo pipefail`, a `say` helper, `export PATH="$HOME/bin:$PATH"`, plain-language messages for each failure the owner met in Stage 0 (state lock: print the `force-unlock` command; missing variable: say which and how to set it).

- [ ] **Step 2: Check the scripts**

Run: `bash -n ops/scripts/20-stage1-foundations.sh && bash -n ops/scripts/smoke-platform.sh && shellcheck ops/scripts/20-stage1-foundations.sh ops/scripts/smoke-platform.sh`
Expected: no output

- [ ] **Step 3: Move `web-dev` to the dev project in Terraform and CI**

Remove `module "web_dev"` and the `dev` host from the prod root. In `web.yml`, give `deploy-dev` `environment: dev` and `deploy-prod` `environment: production`; both read the same variable names from their environment. Trigger `deploy-dev` on pushes to `integration/stage-1` in the same way as in Task 6, with the same `vars.DEPLOY_DEV_ENABLED == 'true'` condition.

- [ ] **Step 4: Write the runbook**

`docs/runbooks/stage-1-foundations.md`: what the script will create and what it costs (nothing while idle); the exact commands for Cloud Shell; what each prompt means; how to run the smoke test; how to undo (delete the dev project). State plainly that applying `envs/prod` destroys the old `web-dev` service in the prod project, that `dev.<domain>` is served from the dev project afterwards with a gap while its certificate is issued, and that production deploys from now on need the owner's approval in the `production` environment.

- [ ] **Step 5: Commit and open the pull request**

```bash
git add ops/scripts docs/runbooks infra/terraform .github/workflows/web.yml
git commit -m "Stage 1 foundations: dev project script, smoke test, runbook"
```
Open the pull request. **Stop here.** Applying Terraform and running the scripts is the owner's step.

- [ ] **Step 6 (owner, in Cloud Shell): apply and smoke-test**

Run: `bash ops/scripts/20-stage1-foundations.sh` then `bash ops/scripts/smoke-platform.sh audhd-neurobiology-dev`
Expected: `SMOKE PASSED` for the dev project, and `terraform plan` reports no changes in both roots afterwards. This step also proves on the real platform that the push receiver accepts Pub/Sub's token after Cloud Run has stripped its signature.

---

### Task 9: Bring `CLAUDE.md` and the README up to date

**Files:**
- Modify: `CLAUDE.md` (commands section), `README.md` (table of paths)

`CLAUDE.md` already exists from the architecture pull request. This task makes it true for the code that now exists.

- [ ] **Step 1: Update `CLAUDE.md`**

In "Commands", replace the placeholder lines for `services/platform-api` with the real ones: `uv sync`, `uv run pytest -m "not integration"`, `uv run pytest -m integration` (with the emulator), `uv run ruff check .`, `uv run mypy src`, `uv run lint-imports`. In "How to add things", add the exact file to touch for: a new event type (`shared/events.py` users call `new_event`; list the type in `docs/architecture/09-events-and-data-model.md`), a handler (`HandlerRegistry.register` in the module's `handlers.py`), a job (the owning module's `jobs.py` `JOBS`; shared jobs in `platform_api/jobs/__init__.py`), a module (`.importlinter` list).

- [ ] **Step 2: Update the README path table**

Add rows for `services/platform-api/`, `infra/terraform/envs/`, `docs/architecture/`, `docs/plans/`.

- [ ] **Step 3: Check links**

Run: `grep -o 'docs/[A-Za-z0-9_./-]*\.md' CLAUDE.md README.md | cut -d: -f2 | sort -u | xargs -I{} test -f {} && echo links-ok`
Expected: `links-ok`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "Docs: commands and paths for the platform service"
```

---

## Exit test for the slice

1. `uv run pytest` passes locally and in CI, including the emulator test.
2. `SMOKE PASSED` on the dev project.
3. `terraform plan` is clean in both roots after apply.
4. Running the smoke test twice leaves one inbox record per event id.
5. The owner has read the runbook and run every step herself.
