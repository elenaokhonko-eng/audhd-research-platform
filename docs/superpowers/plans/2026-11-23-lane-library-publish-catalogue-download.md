# Lane L5 Library · Publish, Catalogue and Download Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner can publish a PDF with its description from her private folder, a signed-in member sees the catalogue with what they may open, and a member who may open an item gets a link to the file that works for ten minutes.

**Architecture:** An item is a small record (`library_items/{sku}`) plus a file in a private bucket. Publishing validates a manifest (`item.yaml`) the owner placed next to the PDF in a staging area of that bucket, copies the file to a path that includes its version, and writes the record. Access is decided from the member's `Access` (tier and bought items), which the entitlement engine supplies. The record store and the bucket are **ports** with in-memory versions for tests.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, `google-cloud-storage`, `google-cloud-firestore`, pytest. No new dependency.

**Spec:** [04 content, library and search](../../architecture/04-content-library-and-search.md) §2 · [contracts](../../contracts/stage-1-launch.md) §2 (the three library routes and `ItemCard`), §3, §5 · [09 data model](../../architecture/09-events-and-data-model.md) §2 (`library_items`) · task cards B1 to B3.

**Lane rules:** change only `services/platform-api/src/platform_api/library/` and `content/`, and their tests under `services/platform-api/tests/library/`. Branch `library/publish-catalogue-download` from `integration/stage-1`. **Start when the Core lane's Tasks 1 to 3 are merged** (you need `entitlements.public.access_for`, `launch_config`, the `Access` model, and `shared.http`); Task 4's routes also need Core's Task 6 (`member_with_terms`) and Task 8 (`admin.public.owner`). Changes to `main.py` and `cli.py` go in one pull request labelled `cross-lane`.

## Global Constraints

- **No research content in this repository**: no PDF, no real title, abstract or price. Test manifests describe invented items (`sample-map`, `sample-guide`); a test "PDF" is the bytes `b"%PDF-1.4\n…"` built in the test.
- The bucket is private. No object is ever made public, and the only way a file leaves is a signed link that expires after **600 seconds**.
- A member's address never appears in a download record, a log line or an event: records and events carry `member_uid`.
- Two buckets. The **staging bucket** is where the owner places item folders: `<prefix>/<sku>/item.yaml` and `<prefix>/<sku>/<file>`. The **library bucket** holds published files at `items/<sku>/<version>/<file>`; the owner cannot write to it, the service can create objects in it and can never overwrite or delete one.
- The access rule (04 §2.3), from the member's `Access`: `free_members` → any signed-in member; `paid` → tier `paid`, or the sku is among `access.items`; `purchase_only` → only when the sku is among `access.items`.
- While the switch `library_open` is off, the three member routes answer 404 `not_found`; the owner's publish route works.
- Settings of this lane are `library/settings.py: LibrarySettings(BaseSettings)` with prefix `PLATFORM_`: `library_bucket: str = ""`, `library_staging_bucket: str = ""`. The account that signs links is read from the service's own credentials, not from a setting.
- Time is passed in (`now`); routes take it from `shared.clock.utcnow()`.
- Check command for every task, in `services/platform-api`: `uv run ruff format tests && uv run pytest -m "not integration" && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run lint-imports`.

## Rulings by the integrator

1. **`publish` takes a staging prefix, not a folder on disk**: `publish(staging_prefix: str, dry_run: bool, actor: str, now) -> PublishReport`. The service cannot see the owner's disk; she copies the item folders into a folder of the staging bucket with one `gcloud storage cp` command from the runbook, then runs `platform-cli library publish`.
2. **The library decides "may open" itself from `Access`**; it does not call `entitlements.can_open`, and it adds no item-access port to the entitlement module. The integrator updates 04 §2.2 to say so.
3. **Each item is published or refused by itself.** One bad manifest does not stop the others; the report names every problem.
4. **`pages` comes from the manifest** (optional, default 0). The service does not parse PDFs.
5. **The stored record nests the file** as 09 §2 says: `file: {bucket, object, sha256, bytes}`; the manifest's own `file` (a name) is kept as `file_name`.
6. **`content.item.published` carries** `content_id` (`library:<sku>`), `source` (`library`), `access`, and also `sku` and `version`. It is published whenever an item **becomes** published: a new item, a new version, or a draft that is switched to published.

## Review Focus

1. **Publishing the same version twice with a changed file.** Refused: the owner must raise the version. Pinned in Task 1.
2. **A manifest that points at a file outside its own folder** (`../other/secret.pdf`). Refused. Pinned in Task 1.
3. **A retired item**: gone from the catalogue, still downloadable by someone who bought it. Pinned in Tasks 2 and 3.
4. **A member scripting downloads.** The 31st in an hour is refused. Pinned in Task 3.
5. **A sku in the address that is not a sku** (`../x`, upper case, very long). 404, and nothing is looked up. Pinned in Task 4.

---

## File Structure

```
services/platform-api/
├─ src/platform_api/library/
│  ├─ settings.py     LibrarySettings
│  ├─ models.py       Manifest, LibraryItem, ItemCard, ItemDetail, SignedLink, PublishReport, ItemOutcome
│  ├─ ports.py        ItemStore, FileStore, DownloadLog  (+ in-memory versions)
│  ├─ runtime.py      Runtime, set_runtime, get_runtime
│  ├─ publishing.py   parse_manifest, publish
│  ├─ reading.py      may_open, card_for, catalogue, item, download_link
│  ├─ adapters.py     FirestoreItemStore, BucketFileStore, FirestoreDownloadLog
│  └─ public.py  http.py
└─ tests/library/  conftest.py  test_publish.py  test_catalogue.py  test_download.py  test_http.py  test_adapters.py
```

---

### Task 1: Publishing

**Files:**
- Create: `library/settings.py`, `models.py`, `ports.py`, `runtime.py`, `publishing.py`; `tests/library/__init__.py`, `conftest.py`, `test_publish.py`
- Modify: `library/public.py`

**Interfaces:**
- Produces:

```python
Kind = Literal["meta_review", "evidence_map", "clinician_one_pager", "guide", "worksheet"]
ItemAccess = Literal["paid", "free_members", "purchase_only"]
ItemStatus = Literal["draft", "published", "retired"]

class Manifest(BaseModel):                     # item.yaml; extra keys are refused
    sku: str                                   # ^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$
    title: str; kind: Kind; abstract: str; version: str    # version: ^\d+\.\d+$
    access: ItemAccess; file: str; status: ItemStatus       # file: a bare name ending .pdf, no "/" or "\"
    series: str | None = None; topics: list[str] = []; audience: list[str] = []
    evidence_status: str | None = None; language: str = "en"; pages: int = 0
    cover: str | None = None; payhip: dict[str, str] | None = None; price_display: str | None = None
    citation: str | None = None; related_urls: list[str] = []

class StoredFile(BaseModel): bucket: str; object: str; sha256: str; bytes: int
class LibraryItem(BaseModel): ...              # the manifest's fields with `file` renamed `file_name`, plus file: StoredFile, published_at, updated_at, updated_by
class ItemOutcome(BaseModel):
    sku: str                                   # the folder's name, so that a manifest that does not parse can still be named
    action: Literal["created", "new_version", "updated", "unchanged", "refused"]; problems: list[str]
class PublishReport(BaseModel):
    dry_run: bool; staging_prefix: str; items: list[ItemOutcome]

def parse_manifest(text: str) -> tuple[Manifest | None, list[str]]: ...     # problems as "<field>: <what is wrong>"
```

- `ports.py`: `ItemStore` (`get(sku)`, `list_all()`, `put(item)`); `FileStore` (`list_dirs(prefix) -> list[str]`: the folder names directly under `prefix + "/"`, so `batch-1` never includes `batch-10`; `read(path) -> bytes | None`; `exists(path) -> bool`; `sha256(path) -> str | None`; `create_from(source: FileStore, src: str, dst: str) -> bool`: copies only if `dst` does not exist and says whether it did; `signed_url(path, ttl: timedelta, now) -> str`); `DownloadLog` (`add(member_uid, sku, version, at)`, `times_since(member_uid, since) -> list[datetime]`: the downloads with `at > since`, oldest first). Each has an in-memory version (`InMemoryFileStore` has `objects: dict[str, bytes]` and signs as `https://files.invalid/<path>?expires=<unix>`). The runtime holds two file stores: `staging` and `files`.
- `publish(staging_prefix, dry_run, actor, now)`: the prefix must match `^[a-z0-9-]{1,40}$` (`ValueError` otherwise). For every folder under it: read `item.yaml` (absent → refused, "item.yaml: missing"); parse (problems → refused); the folder's name must equal the sku ("sku: the folder is named <folder>"); the file must exist in the folder ("file: <name> is not in the folder") and start with `%PDF` ("file: <name> is not a PDF"); compute its SHA-256. Then: no stored item → `created`; stored with a lower version → `new_version`; same version and same hash → `updated` when another field differs, else `unchanged`; same version and another hash → refused ("version: 1.0 is already published with different content; raise the version"); a lower version than the stored one → refused. Unless `dry_run` or refused: `files.create_from(staging, …)` to `items/<sku>/<version>/<file>`; when the destination already exists, its hash must equal the staged file's, else the item is refused ("file: other content is already stored for this version") and nothing is written; then `put` the record; and publish `content.item.published` when the item's status is now `published` and it was not stored as `published` before, or its version is new (ruling 6).
- `library.public.publish` is that function.

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_publish.py
import pytest

from platform_api.library import public as library
from platform_api.library.publishing import parse_manifest
from tests.fixtures.people import T0

PDF = b"%PDF-1.4\nsample\n"
BASE = {"sku": "sample-map", "title": "Sample map", "kind": "evidence_map", "abstract": "An invented item.",
        "version": "1.0", "access": "paid", "file": "sample-map-v1.0.pdf", "status": "published"}


def yaml_of(**over):
    import yaml
    return yaml.safe_dump({**BASE, **over})


def stage(lib, prefix="batch-1", sku="sample-map", pdf=PDF, folder=None, **over):
    manifest = {**BASE, "sku": sku, **over}
    folder = folder or sku
    lib.staging.objects[f"{prefix}/{folder}/item.yaml"] = yaml_of(sku=sku, **over).encode()
    lib.staging.objects[f"{prefix}/{folder}/{manifest['file']}"] = pdf
    return prefix


def run(prefix, dry_run=False):
    return library.publish(prefix, dry_run, "owner:acc-1", T0)


def test_a_good_item_is_copied_recorded_and_announced(lib, ent):
    [outcome] = run(stage(lib)).items
    stored = lib.items.get("sample-map")
    assert (outcome.action, stored.file.object, stored.file.bytes) == ("created", "items/sample-map/1.0/sample-map-v1.0.pdf", len(PDF))
    assert lib.files.exists(stored.file.object) and len(stored.file.sha256) == 64 and stored.file_name == "sample-map-v1.0.pdf"
    [event] = [e for e in ent.bus.published if e.type.endswith("content.item.published")]
    assert event.data == {"content_id": "library:sample-map", "source": "library", "access": "paid", "sku": "sample-map", "version": "1.0"}


def test_a_dry_run_reports_and_writes_nothing(lib, ent):
    report = run(stage(lib), dry_run=True)
    assert [o.action for o in report.items] == ["created"] and lib.items.list_all() == []
    assert not lib.files.exists("items/sample-map/1.0/sample-map-v1.0.pdf") and ent.bus.published == []


@pytest.mark.parametrize(("over", "field"), [({"abstract": None}, "abstract"), ({"kind": "poster"}, "kind"), ({"version": "v1"}, "version"),
                                              ({"title": None}, "title"), ({"file": "../other/secret.pdf"}, "file"),
                                              ({"file": "notes.txt"}, "file"), ({"colour": "red"}, "colour")])
def test_a_bad_manifest_names_the_field(over, field):
    manifest, problems = parse_manifest(yaml_of(**over))
    assert manifest is None and any(p.startswith(f"{field}:") for p in problems)


def test_one_bad_item_does_not_stop_the_others(lib):
    prefix = stage(lib)
    stage(lib, sku="sample-guide", file="g.pdf", kind="poster")
    lib.staging.objects[f"{prefix}/empty-folder/readme.txt"] = b"x"
    outcomes = {o.sku: (o.action, o.problems) for o in run(prefix).items}
    assert outcomes["sample-map"][0] == "created" and outcomes["sample-guide"][0] == "refused"
    assert outcomes["empty-folder"] == ("refused", ["item.yaml: missing"])


def test_the_file_must_be_there_be_a_pdf_and_the_folder_must_match_the_sku(lib):
    prefix = stage(lib, pdf=b"not a pdf")
    assert run(prefix).items[0].problems == ["file: sample-map-v1.0.pdf is not a PDF"]
    del lib.staging.objects[f"{prefix}/sample-map/sample-map-v1.0.pdf"]
    assert run(prefix).items[0].problems == ["file: sample-map-v1.0.pdf is not in the folder"]
    other = stage(lib, prefix="batch-2", folder="wrong-folder")
    assert run(other).items[0].problems == ["sku: the folder is named wrong-folder"]


def test_versions(lib, ent):
    run(stage(lib))
    assert run(stage(lib)).items[0].action == "unchanged"
    assert run(stage(lib, title="Sample map, retitled")).items[0].action == "updated"
    changed = run(stage(lib, pdf=PDF + b"more"))
    assert changed.items[0].action == "refused" and "raise the version" in changed.items[0].problems[0]
    newer = run(stage(lib, pdf=PDF + b"more", version="1.1", file="sample-map-v1.1.pdf"))
    assert newer.items[0].action == "new_version" and lib.items.get("sample-map").version == "1.1"
    assert lib.files.exists("items/sample-map/1.0/sample-map-v1.0.pdf")          # the old version is kept
    assert run(stage(lib, version="1.0")).items[0].action == "refused"           # going back is refused
    assert len([e for e in ent.bus.published if e.type.endswith("content.item.published")]) == 2


def test_a_stored_object_with_other_content_is_never_replaced(lib):
    lib.files.objects["items/sample-map/1.0/sample-map-v1.0.pdf"] = b"%PDF-1.4\nleft by a run that failed\n"
    [outcome] = run(stage(lib)).items
    assert outcome.action == "refused" and outcome.problems == ["file: other content is already stored for this version"]
    assert lib.items.get("sample-map") is None and lib.files.objects["items/sample-map/1.0/sample-map-v1.0.pdf"].endswith(b"failed\n")


def test_one_batch_never_reads_another(lib):
    stage(lib, prefix="batch-10", sku="sample-guide", file="g.pdf")
    assert [o.sku for o in run(stage(lib)).items] == ["sample-map"]


def test_a_draft_is_stored_but_not_announced_and_the_prefix_is_checked(lib, ent):
    run(stage(lib, status="draft"))
    assert lib.items.get("sample-map").status == "draft" and ent.bus.published == []
    assert run(stage(lib)).items[0].action == "updated" and len(ent.bus.published) == 1      # the draft becomes published
    for bad in ("items/sample-map", "../items", "Batch 1", ""):
        with pytest.raises(ValueError):
            run(bad)
```

`tests/library/conftest.py`: fixture `lib` sets the library runtime with in-memory ports on top of the `ent` fixture (`lib.items`, `lib.staging`, `lib.files`, `lib.downloads`, `lib.bus` = `ent.bus`).

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/library/test_publish.py -v`
Expected: FAIL, `No module named 'platform_api.library.publishing'`.

- [ ] **Step 3: Implement**

Read YAML with `yaml.safe_load`. Version comparison is numeric on both parts (`1.10` is after `1.9`). An unquoted `version: 1.10` arrives as a number: the problem text is "version: write it in quotes, for example \"1.10\"". `payhip.url` and every entry of `related_urls` must start with `https://`.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 15 new tests pass (7 manifests, 8 others).

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "library: validate a manifest and publish an item by version, with dry run"
```

---

### Task 2: The catalogue

**Files:**
- Create: `library/reading.py`, `tests/library/test_catalogue.py`
- Modify: `library/models.py`, `public.py`

**Interfaces:**
- Consumes: `Access` from `entitlements.public`.
- Produces: `ItemCard` (contracts §2: `sku`, `title`, `kind`, `abstract`, `version`, `pages`, `access`, `can_open`, `buy_url`), `ItemDetail(item: ItemCard, description: str, citation: str | None)`, `class ItemNotFound(Exception)`, and in `reading.py`:

```python
def may_open(item: LibraryItem, access: Access) -> tuple[bool, Literal["paid_required", "purchase_required"] | None]: ...
def card_for(item: LibraryItem, access: Access) -> ItemCard: ...
def catalogue(access: Access) -> list[ItemCard]: ...
def item(sku: str, access: Access) -> ItemDetail: ...
```

- `catalogue`: items with status `published`, ordered by title without regard to case. `buy_url` is the manifest's `payhip.url` when the member may not open the item and such a URL exists, else `null`.
- `item`: unknown sku or status `draft` → `ItemNotFound`; status `retired` → only for a member who holds `item:<sku>`, else `ItemNotFound`. `description` is the abstract.
- Neither function returns `file`, `file_name` or anything else about where the file is.

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_catalogue.py
import pytest

from platform_api.entitlements.access import access_from
from platform_api.library import public as library
from platform_api.library.reading import ItemNotFound, may_open
from tests.fixtures.people import T0, holdings, record
from tests.library.test_publish import run, stage

FREE, PAID = access_from([], T0), access_from(holdings("ana"), T0)
BUYER = access_from([record("bo", "item", grant="item:sample-map")], T0)


def shelf(lib):
    stage(lib, payhip={"url": "https://example.org/buy/sample-map", "product_key": "k"})
    stage(lib, sku="sample-guide", title="a guide", kind="guide", file="g.pdf", access="free_members")
    stage(lib, sku="sample-book", title="Zeta book", file="b.pdf", access="purchase_only")
    stage(lib, sku="sample-draft", title="Draft", file="d.pdf", status="draft")
    run("batch-1")


def test_a_free_member_sees_every_card_and_what_is_locked(lib):
    shelf(lib)
    cards = library.catalogue(FREE)
    assert [(c.sku, c.can_open) for c in cards] == [("sample-guide", True), ("sample-map", False), ("sample-book", False)]
    assert cards[1].buy_url == "https://example.org/buy/sample-map" and cards[2].buy_url is None
    assert "file" not in cards[0].model_dump() and "file_name" not in cards[0].model_dump()


def test_a_paid_member_opens_paid_items_but_not_purchase_only(lib):
    shelf(lib)
    assert {c.sku: c.can_open for c in library.catalogue(PAID)} == {"sample-guide": True, "sample-map": True, "sample-book": False}
    assert all(c.buy_url is None for c in library.catalogue(PAID) if c.can_open)


def test_a_buyer_opens_what_they_bought(lib):
    shelf(lib)
    assert {c.sku: c.can_open for c in library.catalogue(BUYER)}["sample-map"] is True


@pytest.mark.parametrize(("item_access", "access", "expected"), [
    ("free_members", FREE, (True, None)), ("paid", FREE, (False, "paid_required")), ("paid", PAID, (True, None)),
    ("purchase_only", PAID, (False, "purchase_required")), ("purchase_only", FREE, (False, "purchase_required")),
])
def test_the_access_rule(lib, item_access, access, expected):
    stage(lib, access=item_access)
    run("batch-1")
    assert may_open(lib.items.get("sample-map"), access) == expected


def test_item_detail_and_what_cannot_be_found(lib):
    shelf(lib)
    detail = library.item("sample-map", FREE)
    assert (detail.item.sku, detail.description, detail.item.can_open) == ("sample-map", "An invented item.", False)
    for sku in ("sample-draft", "nope"):
        with pytest.raises(ItemNotFound):
            library.item(sku, PAID)


def test_a_retired_item_leaves_the_catalogue_but_stays_with_its_buyer(lib):
    shelf(lib)
    stage(lib, prefix="batch-2", status="retired")
    run("batch-2")
    assert "sample-map" not in [c.sku for c in library.catalogue(PAID)]
    assert library.item("sample-map", BUYER).item.can_open is True
    with pytest.raises(ItemNotFound):
        library.item("sample-map", PAID)
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/library/test_catalogue.py -v`
Expected: FAIL, `No module named 'platform_api.library.reading'`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 10 new tests pass (5 rule cases, 5 others).

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "library: catalogue and item detail with the access rule"
```

---

### Task 3: The download link

**Files:**
- Create: `tests/library/test_download.py`
- Modify: `library/reading.py`, `models.py`, `public.py`

**Interfaces:**
- Consumes: `entitlements.public.access_for(uid, now)`; `RateLimiter` is not used here: the limit is counted from the download log, so it is exact.
- Produces: `SignedLink(url: str, expires_at: datetime)`; `class NotEntitled(Exception)` with `reason`; `class TooManyDownloads(Exception)` with `retry_after: int`; `library.public.download_link(uid: str, sku: str, now: datetime) -> SignedLink`.
- `download_link`, in order: the item as `item()` finds it (`ItemNotFound`); `may_open` false → `NotEntitled(reason)`; `times_since(uid, now − 3,600 seconds)` has 30 or more entries → `TooManyDownloads` (`retry_after` = seconds until the oldest of them is an hour old). The count and the new record are not one atomic step; a few parallel requests could pass together, which is acceptable for a limit meant against scripted copying; sign the **current** version's object for 600 seconds; add the download record; publish `content.item.downloaded` (`member_uid`, `sku`, `version`); return the link with `expires_at = now + 600 seconds`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_download.py
from datetime import timedelta

import pytest

from platform_api.entitlements import public as ent_api
from platform_api.entitlements.models import ChannelsPatch
from platform_api.library import public as library
from platform_api.library.reading import ItemNotFound, NotEntitled, TooManyDownloads
from tests.fixtures.people import EMAIL, T0, record
from tests.library.test_catalogue import shelf
from tests.library.test_publish import PDF, run, stage


def member(ent, name, *kinds, **over):
    cid = ent_api.upsert_contact(EMAIL[name], ChannelsPatch(platform={"member_uid": f"u-{name}"}))
    ent.store.write(cid, [record(name, k, contact_id=cid, member_uid=f"u-{name}", **over) for k in kinds], [])
    return f"u-{name}"


def test_a_paid_member_gets_a_ten_minute_link_and_the_download_is_recorded(lib, ent):
    shelf(lib)
    link = library.download_link(member(ent, "ana", "stripe_year"), "sample-map", T0)
    assert link.expires_at == T0 + timedelta(seconds=600) and "items/sample-map/1.0/sample-map-v1.0.pdf" in link.url
    assert len(lib.downloads.times_since("u-ana", T0 - timedelta(hours=1))) == 1
    [event] = [e for e in ent.bus.published if e.type.endswith("content.item.downloaded")]
    assert event.data == {"member_uid": "u-ana", "sku": "sample-map", "version": "1.0"}


def test_a_free_member_is_refused_with_the_reason(lib, ent):
    shelf(lib)
    uid = member(ent, "bo")
    with pytest.raises(NotEntitled) as paid:
        library.download_link(uid, "sample-map", T0)
    with pytest.raises(NotEntitled) as bought:
        library.download_link(uid, "sample-book", T0)
    assert (paid.value.reason, bought.value.reason) == ("paid_required", "purchase_required")
    assert library.download_link(uid, "sample-guide", T0).url and len(lib.downloads.times_since(uid, T0 - timedelta(hours=1))) == 1


def test_the_link_is_for_the_current_version(lib, ent):
    shelf(lib)
    stage(lib, prefix="batch-2", pdf=PDF + b"2", version="1.1", file="sample-map-v1.1.pdf")
    run("batch-2")
    assert "items/sample-map/1.1/" in library.download_link(member(ent, "ana", "stripe_year"), "sample-map", T0).url


def test_a_retired_item_stays_open_to_its_buyer_only(lib, ent):
    shelf(lib)
    stage(lib, prefix="batch-2", status="retired")
    run("batch-2")
    assert library.download_link(member(ent, "bo", "item", grant="item:sample-map"), "sample-map", T0).url
    with pytest.raises(ItemNotFound):
        library.download_link(member(ent, "ana", "stripe_year"), "sample-map", T0)


def test_a_grant_that_has_ended_no_longer_opens_paid_items(lib, ent):
    shelf(lib)
    uid = member(ent, "fay", "launch_grant", valid_until=T0 + timedelta(days=1))
    assert library.download_link(uid, "sample-map", T0).url
    with pytest.raises(NotEntitled):
        library.download_link(uid, "sample-map", T0 + timedelta(days=2))


def test_the_thirty_first_download_in_an_hour_is_refused(lib, ent):
    shelf(lib)
    uid = member(ent, "ana", "stripe_year")
    for i in range(30):
        library.download_link(uid, "sample-guide", T0 + timedelta(seconds=i))
    with pytest.raises(TooManyDownloads) as err:
        library.download_link(uid, "sample-guide", T0 + timedelta(minutes=10))
    assert err.value.retry_after == 3000
    assert library.download_link(uid, "sample-guide", T0 + timedelta(hours=1, seconds=1)).url
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/library/test_download.py -v`
Expected: FAIL, `cannot import name 'NotEntitled'`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 6 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "library: signed download link for entitled members, recorded and limited"
```

---

### Task 4: Routes, cloud versions of the ports, and the wiring

**Files:**
- Create: `library/adapters.py`, `tests/library/test_http.py`, `tests/library/test_adapters.py`
- Modify: `library/http.py`
- Cross-lane pull request (label `cross-lane`, reviewed by the Core lane): `main.py` (build the library runtime lazily), `admin/client.py` (method `library_publish(staging_prefix, dry_run)`), `cli.py` (command `library publish --staging-prefix <prefix> [--dry-run]`, which prints one line per item, `<sku>: <action>`, and its problems, and exits 1 when any item was refused), and one test beside Core's CLI tests that replaces `cli.admin_client` and checks the printed lines and the exit code for a report with one created and one refused item.

**Interfaces:**
- Routes, on `library/http.py`'s `router`:

| Route | Dependency | Answers |
| --- | --- | --- |
| `GET /v1/library/items` | `member_with_terms` | `{items: [ItemCard]}` |
| `GET /v1/library/items/{sku}` | `member_with_terms` | `{item, description, citation}`; `ItemNotFound` → 404 |
| `POST /v1/library/items/{sku}/download` | `member_with_terms` | `{url, expires_at}`; `NotEntitled` → 403 `forbidden` with `reason`; `TooManyDownloads` → 429 with `retry_after`; `ItemNotFound` → 404 |
| `POST /v1/admin/library/publish` `{staging_prefix, dry_run}` | `admin.public.owner` | `PublishReport`; a bad prefix → 422 |

  A `sku` in the address that does not match the manifest's pattern gives 404 before anything is looked up; the handler checks it itself (a pattern on the path parameter would answer 422). The 429 has the code `rate_limited`. With `library_open` off, the three member routes give 404. The publish route writes an audit entry through `entitlements.public.write_audit` (actor `owner:<account id>`, subject `admin`, action `library.published` or `library.dry_run`).
- `FirestoreItemStore(client)` (`library_items`), `FirestoreDownloadLog(client)` (`downloads`: `member_uid`, `sku`, `version`, `at`, and `expires_at` = `at` + 365 days, the lifetime the privacy notice gives; the Infra lane's time-to-live policy acts on it), `BucketFileStore(bucket, signer: str, token: Callable[[], str])` where `bucket` is a `google.cloud.storage.Bucket`, and `BucketFileStore.from_default_credentials(bucket_name)`, which takes the signer's address and a refreshed access token from `google.auth.default()`. `signed_url` makes a version-4 signed URL for `GET` without a key file by passing `service_account_email` and `access_token` to `generate_signed_url`, which then signs through the IAM Credentials API (the account needs the role Service Account Token Creator on itself, and that API must be enabled: both go in the hand-over). `create_from` uses `copy_blob` with `if_generation_match=0` and returns false when the precondition fails.

- [ ] **Step 1: Write the failing tests**

```python
# tests/library/test_http.py
from platform_api.entitlements.models import LaunchConfig
from tests.library.test_catalogue import shelf


def test_the_catalogue_and_a_download_for_a_paid_member(lib, ent, member_client):
    shelf(lib)
    client, cookie = member_client("ana")
    items = client.get("/v1/library/items", headers=cookie).json()["items"]
    assert {i["sku"]: i["can_open"] for i in items}["sample-map"] is True
    link = client.post("/v1/library/items/sample-map/download", headers=cookie)
    assert link.status_code == 200 and set(link.json()) == {"url", "expires_at"}


def test_a_free_member_is_told_why(lib, ent, member_client):
    shelf(lib)
    client, cookie = member_client("bo")
    r = client.post("/v1/library/items/sample-map/download", headers=cookie)
    assert r.status_code == 403 and r.json()["error"] == {"code": "forbidden", "message": r.json()["error"]["message"], "retry_after": None, "reason": "paid_required"}


def test_unknown_and_malformed_skus_are_not_found(lib, ent, member_client):
    shelf(lib)
    client, cookie = member_client("ana")
    assert client.get("/v1/library/items/sample-map", headers=cookie).status_code == 200
    for sku in ("nope", "Sample-Map", "a" * 80, "x..y"):
        assert client.get(f"/v1/library/items/{sku}", headers=cookie).status_code == 404
        assert client.post(f"/v1/library/items/{sku}/download", headers=cookie).status_code == 404


def test_the_switch_closes_the_member_routes_but_not_publishing(lib, ent, member_client, owner_client):
    shelf(lib)
    client, cookie = member_client("ana")
    ent.store.put_launch_config(LaunchConfig(join_open=True, library_open=False, required_terms_version="t1", required_privacy_version="p1"))
    assert client.get("/v1/library/items", headers=cookie).status_code == 404
    report = owner_client.post("/v1/admin/library/publish", json={"staging_prefix": "batch-1", "dry_run": True})
    assert report.status_code == 200 and report.json()["dry_run"] is True
    assert owner_client.post("/v1/admin/library/publish", json={"staging_prefix": "items/x", "dry_run": True}).status_code == 422


def test_the_routes_need_a_member_and_accepted_terms(lib, ent, member_client):
    client, cookie = member_client("ana")
    assert client.get("/v1/library/items").status_code == 401
    ent.store.put_launch_config(LaunchConfig(join_open=True, library_open=True, required_terms_version="t2", required_privacy_version="p1"))
    assert client.get("/v1/library/items", headers=cookie).status_code == 409
```

`tests/library/conftest.py` holds two more fixtures, on top of `lib` and `idn`. `member_client(name)`: stores `LaunchConfig(join_open=True, library_open=True, required_terms_version="t1", required_privacy_version="p1")` and a default campaign (`slug="members"`, `audience="public"`, no grant policy, `is_default=True`); writes the person's fixture records under the contact id of their address (`record(name, kind, contact_id=contact_id_for(EMAIL[name]))` for each kind `holdings(name)` has; the contact is created with `upsert_contact` first), because sign-in claims only what waits under that id; signs in through `/v1/session/resolve` with the fake identity provider; accepts the terms; returns the client and the header. `owner_client`: `TestClient(create_app(Settings(owner_accounts=["acc-1"]), Deps(verify_owner=sub_of)))` with the header `Authorization: Bearer <token('acc-1')>`, using the helpers `token` and `sub_of` of `tests/admin/test_admin.py`.

```python
# tests/library/test_adapters.py
from datetime import timedelta

from platform_api.library.adapters import BucketFileStore
from tests.fixtures.people import T0


class FakeBlob:
    def __init__(self, name, log):
        self.name, self.log = name, log

    def generate_signed_url(self, **kwargs):
        self.log.append(kwargs)
        return f"https://storage.example/{self.name}?sig"


class FakeBucket:
    def __init__(self):
        self.log = []

    def blob(self, name):
        return FakeBlob(name, self.log)


def test_a_link_is_signed_for_get_for_the_given_time_without_a_key_file():
    bucket = FakeBucket()
    store = BucketFileStore(bucket, signer="svc@example.iam.gserviceaccount.com", token=lambda: "tok")
    url = store.signed_url("items/sample-map/1.0/f.pdf", timedelta(seconds=600), T0)
    [call] = bucket.log
    assert url.startswith("https://storage.example/items/sample-map/1.0/f.pdf")
    assert (call["version"], call["method"], call["expiration"]) == ("v4", "GET", timedelta(seconds=600))
    assert (call["service_account_email"], call["access_token"]) == ("svc@example.iam.gserviceaccount.com", "tok")


class CopyingBucket(FakeBucket):
    def __init__(self, fail=False):
        super().__init__()
        self.fail, self.copies = fail, []

    def copy_blob(self, blob, destination_bucket, new_name, **kwargs):
        self.copies.append((blob.name, new_name, kwargs))
        if self.fail:
            from google.api_core.exceptions import PreconditionFailed
            raise PreconditionFailed("exists")


def test_a_copy_never_overwrites():
    staging, target = CopyingBucket(), CopyingBucket()
    files = BucketFileStore(target, signer="s", token=lambda: "t")
    assert files.create_from(BucketFileStore(staging, signer="s", token=lambda: "t"), "batch-1/a/f.pdf", "items/a/1.0/f.pdf") is True
    assert staging.copies == [("batch-1/a/f.pdf", "items/a/1.0/f.pdf", {"if_generation_match": 0})]
    refusing = CopyingBucket(fail=True)
    assert files.create_from(BucketFileStore(refusing, signer="s", token=lambda: "t"), "x", "y") is False


def test_importing_the_adapters_creates_no_client(monkeypatch):
    import importlib

    from google.cloud import firestore, storage

    def boom(*a, **k):
        raise AssertionError("a client was created at import")

    monkeypatch.setattr(storage, "Client", boom)
    monkeypatch.setattr(firestore, "Client", boom)
    import platform_api.library.adapters as adapters
    importlib.reload(adapters)
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/library/test_http.py tests/library/test_adapters.py -v`
Expected: FAIL with 404 for the routes and `No module named 'platform_api.library.adapters'`.

- [ ] **Step 3: Implement; open the cross-lane pull request**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 8 new tests pass (5 and 3), and the CLI test in the cross-lane pull request.

- [ ] **Step 5: Commit**

```bash
git add services/platform-api
git commit -m "library: member and owner routes; Firestore and bucket adapters with keyless signing"
```

---

## Exit test for this plan

1. The check command passes in CI on the branch and on the cross-lane branch.
2. A search of the lane's diff finds no PDF, no real title and no address outside `example.org`.
3. The hand-over lists for the Infra lane: the settings `PLATFORM_LIBRARY_BUCKET` and `PLATFORM_LIBRARY_STAGING_BUCKET`; the permissions the API's service account needs (read objects in the staging bucket; read and create objects in the library bucket, never delete; Service Account Token Creator on itself, with the IAM Credentials API enabled); the Firestore index on `downloads` (`member_uid`, `at`); and, for the runbook, the two commands the owner runs to publish (copy the item folders to a folder `<name>` of the staging bucket, then `platform-cli library publish --staging-prefix <name> --dry-run`, then without `--dry-run`).
