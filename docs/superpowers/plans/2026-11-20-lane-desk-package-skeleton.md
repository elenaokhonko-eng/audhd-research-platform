# Lane L6 Desk · Package Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `packages/substack-desk` exists as a Python package that installs and tests by itself, defines the subscriber-directory port and its two data shapes exactly as the contracts page states them, and cannot import the platform.

**Architecture:** A small library with no cloud dependency. A **port** is an interface the platform asks; an **adapter** is one way of answering it. This plan builds the port for "who are the paying subscribers" and a capability matrix that says which adapters exist and whether each is switched on. The first adapter, which reads Substack's export file, is task card D2; it gets its plan when the owner has supplied the export's header line and a few invented sample rows.

**Tech Stack:** Python 3.12, Pydantic v2, uv, ruff, mypy (strict), pytest.

**Spec:** [contracts](../../contracts/stage-1-launch.md) §3 (`SubscriberRecord`, `DirectoryListing`, `SubscriberDirectory`) · `docs/architecture/05-substack-desk.md` (ports, capability matrix) · `docs/architecture/02-membership-and-entitlements.md` §4a · ADR 0009.

**Lane rules:** change only `packages/substack-desk/`. Branch from `integration/stage-1`; one pull request per task. The CI workflow is a separate pull request labelled `cross-lane`.

## Global Constraints

- The package imports nothing from `platform_api` and does not depend on it. It must be extractable into its own repository unchanged.
- No network call anywhere in this plan. No use of Substack's private endpoints, in code or in tests.
- Field names, types and literals of `SubscriberRecord` and `DirectoryListing` are exactly those on the contracts page.
- Test data is invented people at `example.org`.
- Python `>=3.12,<3.13`; ruff with line length 100 and rules `E,F,I,UP,B,S`, with per-file ignores `S101` and `E501` for `tests/**` (tests may use `assert` and long lines); `mypy --strict`.
- Check command for every task: `cd packages/substack-desk && uv run pytest -v && uv run ruff check . && uv run mypy src`.

## Review Focus

1. **A later change makes the package import the platform.** A test reads every source file and fails on any import of `platform_api`, and on any such dependency in `pyproject.toml`. Pinned in Task 1.
2. **An email with capitals or spaces.** `SubscriberRecord` stores the address trimmed and lower-cased, so the platform derives the same contact for the same person. Pinned in Task 2.
3. **A record that says paid but has a free type**, or a listing whose count of rejected rows is negative: refused when the model is built. Pinned in Task 2.
4. **A capability asked for by a name that does not exist**: a clear error naming the known capabilities, not a `KeyError`. Pinned in Task 3.
5. **A switched-off capability used by mistake**: `require` refuses it. Pinned in Task 3.

---

## File Structure

```
packages/substack-desk/
├─ pyproject.toml
├─ README.md                        what the package is, how to run its checks
├─ src/substack_desk/
│  ├─ __init__.py                   __version__
│  ├─ models.py                     SubscriberRecord, DirectoryListing
│  ├─ ports.py                      SubscriberDirectory
│  └─ capabilities.py               Capability, CAPABILITIES, require, CapabilityDisabled, UnknownCapability
└─ tests/
   ├─ test_boundary.py
   ├─ test_models.py
   └─ test_capabilities.py
```

---

### Task 1: A package that stands alone

**Files:**
- Create: `packages/substack-desk/pyproject.toml`, `README.md`, `src/substack_desk/__init__.py`, `tests/test_boundary.py`

**Interfaces:**
- Produces: an installable package `substack-desk` version `0.1.0`; `substack_desk.__version__ == "0.1.0"`.

- [ ] **Step 1: Write the failing test**

```python
# packages/substack-desk/tests/test_boundary.py
import ast
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "substack_desk"


def imported_modules(path: pathlib.Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_version_is_exposed():
    import substack_desk

    assert substack_desk.__version__ == "0.1.0"


def test_no_source_file_imports_the_platform():
    offenders = [
        str(path.relative_to(ROOT))
        for path in SRC.rglob("*.py")
        if any(name == "platform_api" or name.startswith("platform_api.") for name in imported_modules(path))
    ]
    assert offenders == []


def test_the_package_does_not_depend_on_the_platform():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not any("platform" in dep.lower() for dep in project.get("dependencies", []))
```

- [ ] **Step 2: See it fail**

Run: `cd packages/substack-desk && uv run pytest tests/test_boundary.py -v`
Expected: FAIL, there is no project to sync.

- [ ] **Step 3: Write `pyproject.toml`, `__init__.py` and `README.md`**

`pyproject.toml`: name `substack-desk`, version `0.1.0`, `requires-python = ">=3.12,<3.13"`, src layout with a `[build-system]` table (`hatchling`, `packages = ["src/substack_desk"]`) so that uv installs the package and `import substack_desk` works, runtime dependency `pydantic>=2`, dev group `pytest`, `ruff`, `mypy`; ruff and mypy configured as in Global Constraints. Run `uv lock` and commit `uv.lock`. `README.md`: three short sections: what the Desk is (the platform's only way to talk to Substack), what exists today (the port and the capability matrix), how to run the checks.

- [ ] **Step 4: See it pass**

Run the check command.
Expected: 3 passed; no lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/substack-desk
git commit -m "substack-desk: package skeleton that cannot import the platform"
```

---

### Task 2: The two data shapes and the port

**Files:**
- Create: `packages/substack-desk/src/substack_desk/models.py`, `src/substack_desk/ports.py`, `tests/test_models.py`

**Interfaces:**
- Produces, exactly as in [contracts §3](../../contracts/stage-1-launch.md):

```python
SubscriberType = Literal["free", "paid", "comp", "gift", "group_seat", "founding", "lifetime"]

class SubscriberRecord(BaseModel):          # frozen
    email: str
    type: SubscriberType
    plan_interval: Literal["month", "year"] | None
    paid_until: datetime | None
    since: datetime | None

class DirectoryListing(BaseModel):          # frozen
    records: list[SubscriberRecord]
    complete: bool
    rejected_rows: int
    exported_at: datetime

class SubscriberDirectory(Protocol):
    def list_paid(self) -> DirectoryListing: ...
```

- Rules the models enforce:
  - `email` is stored trimmed and lower-cased; a value without exactly one `@`, or with nothing on either side of it, is refused.
  - `paid_until`, `since` and `exported_at` must carry a time zone; a naive datetime is refused.
  - `rejected_rows` is zero or more.
  - `SubscriberRecord.is_paid` (a property): true for every type except `free`.
  - `DirectoryListing` refuses a record whose type is `free`: `list_paid` returns paying readers only.

- [ ] **Step 1: Write the failing tests**

```python
# packages/substack-desk/tests/test_models.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from substack_desk.models import DirectoryListing, SubscriberRecord
from substack_desk.ports import SubscriberDirectory

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def record(**over):
    base = {"email": "ana@example.org", "type": "paid", "plan_interval": "year", "paid_until": NOW, "since": NOW}
    return SubscriberRecord(**{**base, **over})


def test_email_is_trimmed_and_lower_cased():
    assert record(email="  Ana@Example.ORG ").email == "ana@example.org"


@pytest.mark.parametrize("bad", ["ana", "@example.org", "ana@", "a@b@c", ""])
def test_a_value_that_is_not_an_email_is_refused(bad):
    with pytest.raises(ValidationError):
        record(email=bad)


def test_a_time_without_a_zone_is_refused():
    with pytest.raises(ValidationError):
        record(paid_until=datetime(2026, 11, 20))


@pytest.mark.parametrize("kind", ["paid", "comp", "gift", "group_seat", "founding", "lifetime"])
def test_every_type_except_free_is_paid(kind):
    assert record(type=kind).is_paid is True


def test_free_is_not_paid():
    assert record(type="free", plan_interval=None, paid_until=None).is_paid is False


def test_an_unknown_type_is_refused():
    with pytest.raises(ValidationError):
        record(type="vip")


def test_a_record_cannot_be_changed_after_it_is_built():
    with pytest.raises(ValidationError):
        record().email = "other@example.org"


def test_a_listing_holds_paying_readers_only():
    with pytest.raises(ValidationError):
        DirectoryListing(records=[record(type="free", plan_interval=None, paid_until=None)],
                         complete=True, rejected_rows=0, exported_at=NOW)


def test_rejected_rows_cannot_be_negative():
    with pytest.raises(ValidationError):
        DirectoryListing(records=[], complete=True, rejected_rows=-1, exported_at=NOW)


def test_anything_with_list_paid_is_a_directory():
    class Fixed:
        def list_paid(self) -> DirectoryListing:
            return DirectoryListing(records=[record()], complete=True, rejected_rows=0, exported_at=NOW)

    directory: SubscriberDirectory = Fixed()
    assert directory.list_paid().records[0].email == "ana@example.org"
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'substack_desk.models'`.

- [ ] **Step 3: Implement `models.py` and `ports.py`**

Both models use `model_config = ConfigDict(frozen=True)`. Validation lives in field and model validators; no I/O.

- [ ] **Step 4: See them pass**

Run the check command.
Expected: 22 passed in total (3 from Task 1, 19 here); no lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add packages/substack-desk
git commit -m "substack-desk: subscriber record, listing and the directory port"
```

---

### Task 3: The capability matrix

**Files:**
- Create: `packages/substack-desk/src/substack_desk/capabilities.py`, `tests/test_capabilities.py`

**Interfaces:**
- Produces:

```python
Surface = Literal["official", "upload", "private"]   # how the capability reaches Substack

class Capability(BaseModel):                         # frozen
    name: str
    surface: Surface
    enabled: bool
    note: str

CAPABILITIES: Mapping[str, Capability]               # read-only
class UnknownCapability(KeyError): ...
class CapabilityDisabled(RuntimeError): ...
def require(name: str, capabilities: Mapping[str, Capability] = CAPABILITIES) -> Capability: ...
```

- `CAPABILITIES` holds exactly these two entries in this plan:

| Name | Surface | Enabled | Note |
| --- | --- | --- | --- |
| `subscriber_directory.file` | `upload` | true | The owner uploads Substack's export file |
| `subscriber_directory.publisher_api` | `official` | false | Switched on when the publication has the Publisher API and the adapter exists |

- `require` returns the capability when it exists and is enabled; raises `UnknownCapability` whose message lists the known names in alphabetical order; raises `CapabilityDisabled` whose message contains the name.
- No entry with surface `private` may be enabled by default: a test asserts it, so the rule survives later additions ([05](../../architecture/05-substack-desk.md): private endpoints sit behind a switch the owner turns on).

- [ ] **Step 1: Write the failing tests**

```python
# packages/substack-desk/tests/test_capabilities.py
import pytest

from substack_desk.capabilities import (
    CAPABILITIES,
    Capability,
    CapabilityDisabled,
    UnknownCapability,
    require,
)


def test_the_file_directory_is_available():
    assert require("subscriber_directory.file").surface == "upload"


def test_the_publisher_api_is_listed_but_switched_off():
    assert CAPABILITIES["subscriber_directory.publisher_api"].enabled is False
    with pytest.raises(CapabilityDisabled, match="subscriber_directory.publisher_api"):
        require("subscriber_directory.publisher_api")


def test_an_unknown_name_lists_the_known_ones():
    with pytest.raises(UnknownCapability) as err:
        require("notes.publish")
    assert "subscriber_directory.file, subscriber_directory.publisher_api" in str(err.value)


def test_nothing_that_uses_a_private_surface_is_on_by_default():
    assert [c.name for c in CAPABILITIES.values() if c.surface == "private" and c.enabled] == []


def test_the_matrix_cannot_be_changed_at_run_time():
    with pytest.raises(TypeError):
        CAPABILITIES["x"] = Capability(name="x", surface="private", enabled=True, note="")  # type: ignore[index]


def test_require_reads_the_matrix_it_is_given():
    custom = {"a.b": Capability(name="a.b", surface="official", enabled=True, note="")}
    assert require("a.b", custom).name == "a.b"
```

- [ ] **Step 2: See them fail**

Run: `uv run pytest tests/test_capabilities.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'substack_desk.capabilities'`.

- [ ] **Step 3: Implement `capabilities.py`**

`CAPABILITIES` is a `types.MappingProxyType` over a private dict.

- [ ] **Step 4: See them pass**

Run the check command.
Expected: 28 passed in total; no lint or type errors.

- [ ] **Step 5: Commit, and open the cross-lane pull request**

```bash
git add packages/substack-desk
git commit -m "substack-desk: capability matrix with private surfaces off by default"
```

Separately, on a branch `desk/ci`, add `.github/workflows/substack-desk.yml`: on every pull request and on pushes to `main` and `integration/**` that touch `packages/substack-desk/**` or the workflow file; one job that installs uv, then runs `uv sync`, `uv run ruff check .`, `uv run mypy src` and `uv run pytest -v` in `packages/substack-desk`. Open it as a pull request labelled `cross-lane` for the Infra lane to review.

---

## Exit test for this plan

1. The check command passes in `packages/substack-desk` with 28 tests.
2. In a fresh clone, `cd packages/substack-desk && uv sync && uv run pytest` passes without the rest of the repository being installed.
3. No file outside `packages/substack-desk/` changed, except through the one `cross-lane` pull request.

## What comes next in this lane

Task card D2, the export-file adapter: `FileDirectory(path).list_paid()`. It needs the header line of the owner's Substack export (column names only) and three or four invented rows that show which values the file uses for plan and subscriber type. The integrator adds those to the contracts page and writes the plan.
