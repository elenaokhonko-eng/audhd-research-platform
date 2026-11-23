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


class _StandIn:
    """Replaces StripeSdkReader in the jobs' runtime; `for_test` stays the real one."""

    def __init__(self, build):
        self._build, self.for_test = build, adapters.StripeSdkReader.for_test

    def __call__(self, key):
        return self._build(key)


def reader(pages, fail_on=None):
    fake = FakeSubscriptions(pages, fail_on)
    return adapters.StripeSdkReader.for_test(subscriptions=fake), fake


def pages():
    return [json.loads((RECORDED / f"subscriptions_page_{n}.json").read_text()) for n in (1, 2)]


def test_both_recorded_pages_are_read_and_mapped():
    r, fake = reader(pages())
    subs = list(r.subscriptions())
    assert len(subs) == 4 and len(fake.calls) == 2 and fake.calls[0]["status"] == "all"
    settings = CommerceSettings(
        stripe_substack_application=subs[0].application, substack_grant_year="tier:paid"
    )
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
    assert not called & {
        "create",
        "modify",
        "update",
        "delete",
        "cancel",
        "refund",
        "pause",
        "resume",
    }  # so no dict.update() in this file either


def test_the_recorded_pages_hold_only_invented_people():
    text = "".join((RECORDED / f"subscriptions_page_{n}.json").read_text() for n in (1, 2))
    assert (
        "@" not in text.replace("@example.org", "")
        and "sub_test_" in text
        and '"livemode": false' in text
    )


def test_the_jobs_are_registered():
    from platform_api.cli import build_registry

    assert {"stripe-reconcile", "roster-import", "selfcheck"} <= set(build_registry())


# Beyond the brief's five.

from datetime import timedelta  # noqa: E402
from typing import Any  # noqa: E402

from tests.fake_firestore import _MISSING, Collection, FakeFirestore, Query  # noqa: E402


def test_the_recorded_pages_are_mapped_field_by_field():
    from datetime import UTC, datetime

    r, fake = reader(pages())
    subs = {s.id: s for s in r.subscriptions()}
    first, other, deleted, late = (subs[f"sub_test_{n}"] for n in (1, 2, 3, 4))
    assert first.application == "ca_test_substack" and other.application == "ca_test_other"
    assert first.customer_email == "ana@example.org" and first.interval == "year"
    # the period end of the pinned API version is on the first subscription item
    assert first.current_period_end == datetime(2027, 5, 4, tzinfo=UTC)
    assert deleted.customer_email is None
    assert late.status == "past_due" and late.past_due_since == datetime(2026, 11, 10, tzinfo=UTC)
    assert first.past_due_since is None  # only while past_due
    assert all(s.provider_time == T0 for s in subs.values())
    assert fake.calls[0]["limit"] == 100 and "starting_after" not in fake.calls[0]
    assert set(fake.calls[0]["expand"]) == {"data.customer", "data.latest_invoice"}
    assert fake.calls[1]["starting_after"] == "sub_test_2"


def test_a_subscription_that_cannot_be_built_is_one_error_without_its_contents():
    broken = pages()
    broken[0]["data"][0]["status"] = "frozen"
    broken[0]["data"][0]["metadata"] = {"ana@example.org": "ana@example.org"}
    r, _ = reader(broken)
    with pytest.raises(StripeReadError) as err:
        list(r.subscriptions())
    assert str(err.value) == "ValidationError" and err.value.__cause__ is None
    assert "@" not in repr(err.value) and err.value.args == ("ValidationError",)


def test_a_subscription_without_items_or_customer_is_one_error():
    for change in ("items", "customer"):
        broken = pages()
        del broken[1]["data"][0][change]
        r, _ = reader(broken)
        with pytest.raises(StripeReadError) as err:
            list(r.subscriptions())
        assert str(err.value) == "KeyError" and err.value.__cause__ is None


def test_a_page_that_says_more_but_holds_none_is_an_error():
    empty = pages()
    empty[0]["data"] = []
    r, fake = reader(empty)
    with pytest.raises(StripeReadError):
        list(r.subscriptions())
    assert len(fake.calls) == 1


def test_the_reader_pins_the_api_version_it_was_written_for():
    import stripe

    text = Path(adapters.__file__).read_text()
    assert stripe.VERSION == "17.1.0" and stripe.api_version in text


# The Firestore stores, on Core's fake client with ordering and limits added. As in Firestore,
# an order on a field leaves out documents without it and puts null before every value.


class OrderedQuery(Query):
    def __init__(self, db, collection, filters=(), order=None, direction="ASCENDING", cap=None):
        super().__init__(db, collection, filters, order)
        self._direction, self._cap = direction, cap

    def _with(self, **changes):
        state = dict(
            filters=self._filters, order=self._order, direction=self._direction, cap=self._cap
        )
        state.update(changes)
        return OrderedQuery(self._db, self._collection, **state)

    def where(self, *, filter):
        return self._with(filters=(*self._filters, filter))

    def order_by(self, field, direction="ASCENDING"):
        return self._with(order=field, direction=direction)

    def limit(self, n):
        return self._with(cap=n)

    def stream(self, transaction=None):
        self._db.queries.append(
            (
                self._collection,
                tuple(sorted((f.field_path, f.op_string) for f in self._filters)),
                self._order,
                self._direction,
            )
        )
        found = Query(self._db, self._collection, self._filters).stream()
        if self._order is not None:
            found = [s for s in found if self._value(s.to_dict(), self._order) is not _MISSING]

            def key(s):
                value = self._value(s.to_dict(), self._order)
                return (value is not None, value if value is not None else 0)

            found.sort(key=key, reverse=self._direction == "DESCENDING")
        return found if self._cap is None else found[: self._cap]


class OrderedCollection(OrderedQuery, Collection):
    pass


class OrderedFirestore(FakeFirestore):
    def __init__(self):
        super().__init__()
        self.queries = []

    def collection(self, name):
        return OrderedCollection(self, name)


# The composite indexes the Infra lane creates on sync_runs
# (infra/terraform/modules/firestore_schema/main.tf), each ending in `finished_at` descending.
INDEXES = [("kind",), ("kind", "state", "dry_run"), ("kind", "dry_run")]


def _queries_are_served_by_the_indexes(db):
    """Every sync_runs query: equality filters only, and either no order (served by the
    single-field indexes) or an order on `finished_at` descending over exactly the fields of
    one composite index (or none, for the single-field index of `finished_at`)."""
    seen = [q for q in db.queries if q[0] == "sync_runs"]
    assert seen
    for _, filters, order, direction in seen:
        assert all(op == "==" for _, op in filters), filters
        if order is None:
            continue
        assert order == "finished_at" and direction == "DESCENDING"
        fields = {f for f, _ in filters}
        assert fields == set() or any(fields == set(index) for index in INDEXES), filters


def test_the_real_latest_run_is_read_with_the_kind_and_dry_run_index():
    from platform_api.commerce.adapters import FirestoreRunStore

    db = OrderedFirestore()
    store = FirestoreRunStore(db)
    _runs_on(store)
    db.queries.clear()
    store.latest("stripe_reconcile", real_only=True)
    ordered = [(f, o) for c, f, o, _ in db.queries if o is not None]
    assert ordered == [((("dry_run", "=="), ("kind", "==")), "finished_at")]


def _runs_on(store):
    """Real and dry runs of both kinds, finished and not; the last one still running."""
    s = lambda minutes: T0 + timedelta(minutes=minutes)  # noqa: E731
    a = store.start("stripe_reconcile", False, "schedule", s(0))
    store.finish(a, "completed", "passed", {"seen": 4}, s(1))
    b = store.start("stripe_reconcile", True, "owner", s(2))
    store.finish(b, "completed", "passed", {"seen": 4}, s(3))
    c = store.start("roster_import", False, "owner", s(4))
    store.finish(c, "failed", None, {}, s(5))
    d = store.start("stripe_reconcile", False, "schedule", s(6))
    store.finish(d, "failed", None, {"seen": 1}, s(7))
    e = store.start("stripe_reconcile", False, "schedule", s(8))
    store.finish(e, "completed", "blocked", {"seen": 4}, s(9))
    store.start("stripe_reconcile", True, "owner", s(10))  # an unfinished dry run
    store.start("stripe_reconcile", False, "member", s(11))  # still running


def _shape(run):
    return None if run is None else run.model_dump(exclude={"run_id"})


def test_the_firestore_run_store_answers_as_the_in_memory_one():
    from platform_api.commerce.adapters import FirestoreRunStore
    from platform_api.commerce.ports import InMemoryRunStore

    db = OrderedFirestore()
    cloud, memory = FirestoreRunStore(db), InMemoryRunStore()
    _runs_on(cloud), _runs_on(memory)
    for kind in ("stripe_reconcile", "roster_import"):
        for completed_only in (False, True):
            for real_only in (False, True):
                flags = dict(completed_only=completed_only, real_only=real_only)
                assert _shape(cloud.latest(kind, **flags)) == _shape(memory.latest(kind, **flags))
    for kind in ("stripe_reconcile", "roster_import", None):
        for limit in (1, 3, 20):
            got = [_shape(r) for r in cloud.recent(kind, limit)]
            assert got == [_shape(r) for r in memory.recent(kind, limit)]
    _queries_are_served_by_the_indexes(db)


def test_a_run_round_trips_and_its_document_holds_counts_only():
    from platform_api.commerce.adapters import FirestoreRunStore

    db = OrderedFirestore()
    store = FirestoreRunStore(db)
    run_id = store.start("stripe_reconcile", False, "schedule", T0)
    assert store.get(run_id).state == "running" and store.get(run_id).finished_at is None
    store.finish(run_id, "completed", "passed", {"seen": 2, "unseen": 0}, T0 + timedelta(1))
    run = store.get(run_id)
    assert (run.state, run.guard, run.counts) == ("completed", "passed", {"seen": 2, "unseen": 0})
    assert run.finished_at == T0 + timedelta(1) and store.get("no-such-run") is None
    assert db.docs[("sync_runs", run_id)]["kind"] == "stripe_reconcile"


def test_the_start_slot_is_taken_once_per_gap_in_a_transaction():
    from platform_api.commerce.adapters import FirestoreRunStore

    db = OrderedFirestore()
    store, gap = FirestoreRunStore(db), timedelta(seconds=60)
    assert store.acquire_start_slot("stripe_reconcile", T0, gap) is True
    assert store.acquire_start_slot("stripe_reconcile", T0 + timedelta(seconds=59), gap) is False
    assert store.acquire_start_slot("roster_import", T0, gap) is True  # each kind its own
    assert store.acquire_start_slot("stripe_reconcile", T0 + timedelta(seconds=60), gap) is True
    assert ("config", "reconcile_slot") in db.docs
    db.abort_commits = True
    with pytest.raises(RuntimeError, match="gave up"):
        store.acquire_start_slot("stripe_reconcile", T0 + timedelta(hours=1), gap)


def _promotion(**changes):
    from platform_api.commerce.models import Promotion

    fields: dict[str, Any] = dict(
        id="offer-1",
        channel="substack_offer",
        audience=["free_members"],
        plan_interval="year",
        starts_at=T0,
        ends_at=T0 + timedelta(days=7),
        substack_offer_url="https://example.org/offer",
        display={"headline": "An offer"},
        updated_at=T0,
        updated_by="owner:acc-1",
    )
    return Promotion(**{**fields, **changes})


def test_promotions_keep_their_counts_and_count_each_pair_once():
    from platform_api.commerce.adapters import FirestorePromotionStore

    db = OrderedFirestore()
    store = FirestorePromotionStore(db)
    store.put_all([_promotion()])
    assert store.count_once("offer-1", "c-1") is True
    assert store.count_once("offer-1", "c-1") is False
    assert store.count_once("offer-2", "c-1") is False  # no such promotion
    assert ("promotion_upgrades", "offer-1:c-1") in db.docs
    store.put_all([_promotion(display={"headline": "Changed"}), _promotion(id="offer-2")])
    held = {p.id: p for p in store.list()}
    assert held["offer-1"].counts == {"upgrades_in_window": 1}
    assert held["offer-1"].display == {"headline": "Changed"} and held["offer-2"].counts == {}


def test_a_stored_promotion_with_a_field_the_model_does_not_declare_is_read():
    from platform_api.commerce.adapters import FirestorePromotionStore

    db = OrderedFirestore()
    store = FirestorePromotionStore(db)
    store.put_all([_promotion()])
    db.docs[("promotions", "offer-1")]["stripe_coupon_id"] = "later"
    assert [p.id for p in store.list()] == ["offer-1"]


def test_a_count_that_cannot_commit_raises_and_counts_nothing():
    from platform_api.commerce.adapters import FirestorePromotionStore

    db = OrderedFirestore()
    store = FirestorePromotionStore(db)
    store.put_all([_promotion()])
    db.abort_commits = True
    with pytest.raises(RuntimeError):
        store.count_once("offer-1", "c-1")
    assert store.list()[0].counts == {} and ("promotion_upgrades", "offer-1:c-1") not in db.docs
    db.abort_commits = False
    for bad in ("offer/1", "offer:1"):
        with pytest.raises(ValueError):
            store.count_once(bad, "c-1")


# Cloud Run, the bucket and Secret Manager, with stand-ins for their clients.


def test_the_job_starter_starts_without_waiting_and_hides_the_error():
    from google.api_core.exceptions import PermissionDenied

    from platform_api.commerce.adapters import CloudRunJobStarter
    from platform_api.commerce.ports import JobStartError

    class Jobs:
        def __init__(self, fail=False):
            self.calls, self.fail = [], fail

        def run_job(self, **kwargs):
            self.calls.append(kwargs)
            if self.fail:
                raise PermissionDenied("caller sa@example.org may not run projects/p/jobs/j")
            return object()  # an operation nobody waits for

    jobs = Jobs()
    CloudRunJobStarter(jobs).start("projects/p/locations/l/jobs/stripe-reconcile")
    assert jobs.calls == [{"name": "projects/p/locations/l/jobs/stripe-reconcile", "timeout": 10}]
    with pytest.raises(JobStartError) as err:
        CloudRunJobStarter(Jobs(fail=True)).start("projects/p/locations/l/jobs/stripe-reconcile")
    assert "@" not in str(err.value) and "projects/" not in str(err.value)
    assert err.value.__cause__ is None


class Blob:
    def __init__(self, name, updated, data=b"Email,Stripe plan\n"):
        self.name, self.updated, self._data = name, updated, data

    def download_as_bytes(self):
        return self._data


class Storage:
    def __init__(self, *blobs):
        self.blobs, self.asked = blobs, []

    def list_blobs(self, bucket):
        self.asked.append(bucket)
        return iter(self.blobs)


def test_the_roster_inbox_gives_the_newest_object_or_none():
    from platform_api.commerce.adapters import BucketRosterInbox

    older = Blob("export-1.csv", T0, b"old")
    newer = Blob("export-2.csv", T0 + timedelta(hours=1), b"new")
    storage = Storage(newer, older)
    found = BucketRosterInbox(storage, "inbox").newest()
    assert (found.name, found.data, found.updated_at) == ("export-2.csv", b"new", newer.updated)
    assert storage.asked == ["inbox"]
    assert BucketRosterInbox(Storage(), "inbox").newest() is None


class Secrets:
    def __init__(self, value=b"rk_test_0123456789abcdefghij", fail=False):
        self.value, self.fail, self.asked = value, fail, []

    def access_secret_version(self, **kwargs):
        self.asked.append(kwargs)
        if self.fail:
            from google.api_core.exceptions import NotFound

            raise NotFound(f"no secret {kwargs['name']}")
        payload = type("P", (), {"data": self.value})()
        return type("R", (), {"payload": payload})()


def test_a_secret_is_read_from_its_latest_version_and_never_shown():
    from platform_api.commerce.adapters import read_secret

    secrets = Secrets()
    assert read_secret("projects/p/secrets/stripe-read-key", client=secrets).startswith("rk_test_")
    full = "projects/p/secrets/stripe-read-key/versions/latest"
    read_secret(full, client=secrets)
    assert [a["name"] for a in secrets.asked] == [full, full]
    for broken in (Secrets(fail=True), Secrets(value=b"rk_test_\xff\xfe0123456789")):
        with pytest.raises(RuntimeError) as err:
            read_secret(full, client=broken)
        assert "rk_test" not in str(err.value) and "projects/" not in str(err.value)
        assert err.value.__cause__ is None


# The two jobs.


@pytest.fixture
def cloud(ent, monkeypatch):
    """The jobs' cloud clients replaced: a fake Firestore, an in-memory bus, the recorded
    pages for Stripe, and a secret read that is recorded."""
    from platform_api.commerce import adapters as cloud_adapters
    from platform_api.commerce import jobs
    from platform_api.commerce import runtime as runtime_module

    monkeypatch.setattr(runtime_module, "_runtime", None)
    db = OrderedFirestore()
    seen: dict[str, Any] = {"secrets": [], "keys": [], "db": db, "pages": pages()}
    monkeypatch.setattr(jobs, "_clients", lambda settings: (ent.bus, db))

    def read_secret(name):
        seen["secrets"].append(name)
        return "rk_test_0123456789abcdefghij"

    def stripe_reader(key):
        seen["keys"].append(key)
        return reader(seen["pages"], seen.get("fail_on"))[0]

    monkeypatch.setattr(cloud_adapters, "read_secret", read_secret)
    # build_runtime imports the reader from its module when it is given a key
    monkeypatch.setattr(adapters, "StripeSdkReader", _StandIn(stripe_reader))
    monkeypatch.setenv("PLATFORM_STRIPE_KEY_SECRET", "projects/p/secrets/k/versions/latest")
    monkeypatch.setenv("PLATFORM_STRIPE_SUBSTACK_APPLICATION", "ca_test_substack")
    return seen


def _job(name, capsys):
    from platform_api.commerce.jobs import JOBS
    from platform_api.settings import Settings

    code = JOBS[name](Settings())
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    return code, json.loads(lines[0])


def test_the_reconcile_job_reads_the_key_runs_and_prints_the_run(cloud, capsys):
    code, run = _job("stripe-reconcile", capsys)
    assert code == 0 and run["state"] == "completed" and run["guard"] == "passed"
    assert (run["kind"], run["dry_run"], run["requested_by"]) == (
        "stripe_reconcile",
        False,
        "schedule",
    )
    assert cloud["secrets"] == ["projects/p/secrets/k/versions/latest"]
    assert cloud["keys"] == ["rk_test_0123456789abcdefghij"]
    assert run["counts"]["seen"] == 4 and "@" not in json.dumps(run)
    assert ("sync_runs", run["run_id"]) in cloud["db"].docs


def test_a_dry_run_asked_by_the_owner_is_recorded_so(cloud, capsys, monkeypatch, ent):
    monkeypatch.setenv("PLATFORM_JOB_DRY_RUN", "1")
    monkeypatch.setenv("PLATFORM_JOB_REQUESTED_BY", "owner")
    code, run = _job("stripe-reconcile", capsys)
    assert code == 0 and run["dry_run"] is True and run["requested_by"] == "owner"
    assert ent.store.entitlements_by_source("substack_stripe") == []


def test_a_failed_read_exits_1(cloud, capsys):
    cloud["fail_on"] = 1
    code, run = _job("stripe-reconcile", capsys)
    assert code == 1 and run["state"] == "failed"


def test_exit_codes_follow_the_run():
    from platform_api.commerce.jobs import exit_code
    from platform_api.commerce.models import SyncRun

    def run(state, guard):
        return SyncRun(
            run_id="r",
            kind="stripe_reconcile",
            dry_run=False,
            state=state,
            guard=guard,
            requested_by="schedule",
            counts={},
            started_at=T0,
            finished_at=T0,
        )

    assert exit_code(run("completed", "passed")) == 0
    assert exit_code(run("failed", None)) == 1
    assert exit_code(run("completed", "blocked")) == 2
    assert exit_code(run("running", None)) == 1


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("PLATFORM_JOB_DRY_RUN", "true"),
        ("PLATFORM_JOB_REQUESTED_BY", "ana@example.org"),
        ("PLATFORM_STRIPE_KEY_SECRET", ""),
    ],
)
def test_a_job_that_cannot_start_exits_1_naming_the_class_only(
    cloud, capsys, monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    code, line = _job("stripe-reconcile", capsys)
    assert code == 1 and set(line) == {"job", "error"} and "@" not in json.dumps(line)
    assert cloud["db"].docs == {}  # no run was started, so none is left running


def test_a_secret_that_cannot_be_read_stops_the_job_before_any_run(cloud, capsys, monkeypatch):
    from platform_api.commerce import adapters as cloud_adapters

    def broken(name):
        raise RuntimeError("the secret could not be read")

    monkeypatch.setattr(cloud_adapters, "read_secret", broken)
    code, line = _job("stripe-reconcile", capsys)
    assert (code, line) == (1, {"job": "stripe-reconcile", "error": "RuntimeError"})
    assert cloud["db"].docs == {}


def test_the_sandbox_marker_in_prod_stops_the_job_before_the_secret(cloud, capsys, monkeypatch):
    monkeypatch.setenv("PLATFORM_ENV", "prod")
    monkeypatch.setenv("PLATFORM_STRIPE_TEST_CHANNEL_METADATA", "true")
    code, line = _job("stripe-reconcile", capsys)
    assert code == 1 and line["error"] == "ValidationError" and cloud["secrets"] == []


def test_the_roster_job_never_reads_the_stripe_key(cloud, capsys, monkeypatch):
    from platform_api.commerce import adapters as cloud_adapters

    storage = Storage()
    monkeypatch.setattr(cloud_adapters, "_storage_client", lambda: storage)
    monkeypatch.setenv("PLATFORM_ROSTER_INBOX_BUCKET", "inbox")
    code, run = _job("roster-import", capsys)
    # no reconcile has passed in the last day: the import refuses, and says so
    assert code == 1 and run["kind"] == "roster_import" and run["state"] == "failed"
    assert cloud["secrets"] == [] and cloud["keys"] == []


def test_the_runtime_for_the_api_holds_no_stripe_reader_and_builds_no_client(monkeypatch):
    from platform_api.commerce import adapters as cloud_adapters
    from platform_api.shared.bus import InMemoryBus
    from platform_api.shared.ratelimit import InMemoryRateLimiter

    def no_client():
        raise AssertionError("a client was built")

    monkeypatch.setattr(cloud_adapters, "_storage_client", no_client)
    monkeypatch.setattr(cloud_adapters, "_jobs_client", no_client)
    settings = CommerceSettings(reconcile_job="projects/p/locations/l/jobs/stripe-reconcile")
    lazy_db = type("NoDb", (), {"collection": lambda self, name: no_client()})()
    runtime = cloud_adapters.build_runtime(
        settings, InMemoryBus(), lazy_db, stripe_key=None, limiter=InMemoryRateLimiter()
    )
    assert runtime.stripe is None and runtime.jobs is not None and runtime.inbox is None


# The owner's run listing.


def _seed(com, n):
    for i in range(n):
        run_id = com.runs.start("stripe_reconcile", False, "schedule", T0 + timedelta(minutes=i))
        com.runs.finish(run_id, "completed", "passed", {"seen": i}, T0 + timedelta(minutes=i))
    com.runs.start("roster_import", True, "owner", T0)


def test_the_owner_lists_the_latest_runs(com, owner_client):
    _seed(com, 25)
    runs = owner_client.get("/v1/admin/sync-runs").json()["runs"]
    assert len(runs) == 20 and runs[0]["counts"] == {"seen": 24}
    only = owner_client.get("/v1/admin/sync-runs", params={"kind": "roster_import"}).json()
    assert [r["kind"] for r in only["runs"]] == ["roster_import"]
    assert len(owner_client.get("/v1/admin/sync-runs?limit=2").json()["runs"]) == 2
    for bad in ("limit=21", "limit=0", "kind=payhip"):
        assert owner_client.get(f"/v1/admin/sync-runs?{bad}").status_code == 422


def test_listing_runs_is_audited_and_refused_to_anyone_else(com, owner_client, ent):
    from tests.admin.test_admin import token

    assert owner_client.get("/v1/admin/sync-runs").status_code == 200
    assert owner_client.get("/v1/admin/sync-runs?limit=21").status_code == 422
    for headers in ({"Authorization": ""}, {"Authorization": f"Bearer {token('acc-2')}"}):
        assert owner_client.get("/v1/admin/sync-runs", headers=headers).status_code == 403
    entries = [(a.actor, a.action, a.subject, a.evidence) for a in ent.store.audit_for("admin")]
    assert entries == [
        ("owner:acc-1", "admin.read", "admin", {"route": "sync-runs", "outcome": "200"}),
        ("owner:acc-1", "admin.read", "admin", {"route": "sync-runs", "outcome": "422"}),
    ]


def test_importing_the_adapters_does_not_import_stripe():
    import subprocess
    import sys

    probe = "import sys, platform_api.commerce.adapters; assert 'stripe' not in sys.modules"
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)  # noqa: S603
    assert done.returncode == 0, done.stderr[-400:]


def test_a_failure_after_the_run_started_finishes_it_as_failed(cloud, capsys, monkeypatch):
    from platform_api.commerce import adapters as cloud_adapters

    real_finish = cloud_adapters.FirestoreRunStore.finish
    calls = []

    def finish_fails_once(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError("firestore unavailable")
        return real_finish(self, *args, **kwargs)

    monkeypatch.setattr(cloud_adapters.FirestoreRunStore, "finish", finish_fails_once)
    code, line = _job("stripe-reconcile", capsys)
    assert code == 1 and set(line) == {"job", "run_id", "error"}
    assert line["error"] == "RuntimeError"
    stored = cloud["db"].docs[("sync_runs", line["run_id"])]
    assert stored["state"] == "failed" and stored["counts"]["seen"] == 4


def test_a_run_that_finished_is_not_marked_failed_afterwards(cloud, capsys, monkeypatch):
    from platform_api.commerce import adapters as cloud_adapters

    real_get = cloud_adapters.FirestoreRunStore.get
    asked = []

    def get_misses_once(self, run_id):  # the run's own read misses; the job's check does not
        asked.append(run_id)
        return None if len(asked) == 1 else real_get(self, run_id)

    monkeypatch.setattr(cloud_adapters.FirestoreRunStore, "get", get_misses_once)
    code, line = _job("stripe-reconcile", capsys)
    assert code == 1 and set(line) == {"job", "run_id", "error"}
    assert cloud["db"].docs[("sync_runs", line["run_id"])]["state"] == "completed"


def test_a_promotion_id_that_could_make_two_upgrade_keys_alike_is_refused(com, owner_client):
    body = {**_promotion().model_dump(mode="json"), "id": "a:b"}
    assert owner_client.put("/v1/admin/promotions", json={"promotions": [body]}).status_code == 422
    for bad in ("a:b", "a/b"):
        with pytest.raises(ValueError):
            _promotion(id=bad)


# Branch review fixes.


def test_a_secret_error_names_the_class_only():
    from platform_api.commerce.adapters import read_secret

    full = "projects/p/secrets/stripe-read-key/versions/latest"
    for broken, name in (
        (Secrets(fail=True), "NotFound"),
        (Secrets(value=b"rk_test_\xff\xfe0123456789"), "UnicodeDecodeError"),
    ):
        with pytest.raises(RuntimeError) as err:
            read_secret(full, client=broken)
        assert str(err.value) == f"the secret could not be read ({name})"
        assert err.value.__cause__ is None and err.value.__suppress_context__


def test_the_stripe_library_logs_only_warnings_and_above():
    import logging

    import platform_api.commerce.stripe_adapter  # noqa: F401

    assert logging.getLogger("stripe").level == logging.WARNING


@pytest.fixture
def ticking(monkeypatch):
    """A clock the test moves: `ticking[0]` is now."""
    from platform_api.shared import clock

    current = [T0]
    monkeypatch.setattr(clock, "utcnow", lambda: current[0])
    return current


def test_a_run_records_the_time_it_really_finished(cloud, capsys, monkeypatch, ticking):
    real_page = adapters.page_from_json

    def slow_page(data):
        if ticking[0] == T0:
            ticking[0] = T0 + timedelta(minutes=5)  # the read takes five minutes
        return real_page(data)

    monkeypatch.setattr(adapters, "page_from_json", slow_page)
    code, run = _job("stripe-reconcile", capsys)
    stored = cloud["db"].docs[("sync_runs", run["run_id"])]
    assert code == 0 and stored["started_at"] == T0
    assert stored["finished_at"] == T0 + timedelta(minutes=5)


def test_a_failure_after_start_is_finished_at_the_real_time(cloud, capsys, monkeypatch, ticking):
    from platform_api.commerce import adapters as cloud_adapters

    real_finish = cloud_adapters.FirestoreRunStore.finish
    calls = []

    def finish_fails_once(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            ticking[0] = T0 + timedelta(minutes=5)
            raise RuntimeError("firestore unavailable")
        return real_finish(self, *args, **kwargs)

    monkeypatch.setattr(cloud_adapters.FirestoreRunStore, "finish", finish_fails_once)
    code, line = _job("stripe-reconcile", capsys)
    stored = cloud["db"].docs[("sync_runs", line["run_id"])]
    assert code == 1 and stored["finished_at"] == T0 + timedelta(minutes=5)


def test_sigterm_becomes_job_stopped():
    import signal

    from platform_api.commerce.jobs import JobStopped, stop_on_sigterm

    before = signal.getsignal(signal.SIGTERM)
    with pytest.raises(JobStopped):
        with stop_on_sigterm():
            signal.raise_signal(signal.SIGTERM)
    assert signal.getsignal(signal.SIGTERM) == before  # put back afterwards


def test_a_job_stopped_by_cloud_run_fails_its_run(cloud, capsys, monkeypatch, caplog):
    import signal

    real_page = adapters.page_from_json

    def stopped(data):
        signal.raise_signal(signal.SIGTERM)  # Cloud Run stops the job during the read
        return real_page(data)

    monkeypatch.setattr(adapters, "page_from_json", stopped)
    code, run = _job("stripe-reconcile", capsys)
    assert code == 1 and run["state"] == "failed"
    assert cloud["db"].docs[("sync_runs", run["run_id"])]["state"] == "failed"
    assert any("alert=reconcile_failed" in r.getMessage() for r in caplog.records)


def test_a_stop_that_escapes_the_run_still_fails_it(cloud, capsys, monkeypatch):
    from platform_api.commerce import adapters as cloud_adapters
    from platform_api.commerce.jobs import JobStopped

    real_finish = cloud_adapters.FirestoreRunStore.finish
    calls = []

    def stopped_while_finishing(self, *args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise JobStopped
        return real_finish(self, *args, **kwargs)

    monkeypatch.setattr(cloud_adapters.FirestoreRunStore, "finish", stopped_while_finishing)
    code, line = _job("stripe-reconcile", capsys)
    assert (code, line["error"]) == (1, "JobStopped")
    assert cloud["db"].docs[("sync_runs", line["run_id"])]["state"] == "failed"


# Branch review of 6b.


def test_a_job_that_cannot_start_is_logged_by_class_only(caplog):
    import logging

    from google.api_core.exceptions import PermissionDenied

    from platform_api.commerce.adapters import CloudRunJobStarter
    from platform_api.commerce.ports import JobStartError

    class Jobs:
        def run_job(self, **kwargs):
            raise PermissionDenied("caller sa@example.org may not run projects/p/jobs/j")

    with caplog.at_level(logging.WARNING), pytest.raises(JobStartError):
        CloudRunJobStarter(Jobs()).start("projects/p/locations/l/jobs/stripe-reconcile")
    lines = [r.getMessage() for r in caplog.records]
    assert lines == ["refresh_job_not_started error=PermissionDenied"]


def test_the_reconcile_job_setting_is_a_job_resource_name():
    from pydantic import ValidationError

    assert CommerceSettings(reconcile_job="").reconcile_job == ""
    ok = "projects/p/locations/l/jobs/stripe-reconcile"
    assert CommerceSettings(reconcile_job=ok).reconcile_job == ok
    for bad in (
        "stripe-reconcile",
        "projects/p/locations/l/jobs/",
        "projects/p/locations/l/jobs/a/b",
        "projects/p/jobs/stripe-reconcile",
    ):
        with pytest.raises(ValidationError):
            CommerceSettings(reconcile_job=bad)
