import pytest

from platform_api.library import public as library
from platform_api.library.publishing import parse_manifest
from tests.fixtures.people import T0

PDF = b"%PDF-1.4\nsample\n"
BASE = {
    "sku": "sample-map",
    "title": "Sample map",
    "kind": "evidence_map",
    "abstract": "An invented item.",
    "version": "1.0",
    "access": "paid",
    "file": "sample-map-v1.0.pdf",
    "status": "published",
}


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
    assert (outcome.action, stored.file.object, stored.file.bytes) == (
        "created",
        "items/sample-map/1.0/sample-map-v1.0.pdf",
        len(PDF),
    )
    assert (
        lib.files.exists(stored.file.object)
        and len(stored.file.sha256) == 64
        and stored.file_name == "sample-map-v1.0.pdf"
    )
    [event] = [e for e in ent.bus.published if e.type.endswith("content.item.published")]
    assert event.data == {
        "content_id": "library:sample-map",
        "source": "library",
        "access": "paid",
        "sku": "sample-map",
        "version": "1.0",
    }


def test_a_dry_run_reports_and_writes_nothing(lib, ent):
    report = run(stage(lib), dry_run=True)
    assert [o.action for o in report.items] == ["created"] and lib.items.list_all() == []
    assert (
        not lib.files.exists("items/sample-map/1.0/sample-map-v1.0.pdf") and ent.bus.published == []
    )


@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"abstract": None}, "abstract"),
        ({"kind": "poster"}, "kind"),
        ({"version": "v1"}, "version"),
        ({"title": None}, "title"),
        ({"file": "../other/secret.pdf"}, "file"),
        ({"file": "notes.txt"}, "file"),
        ({"colour": "red"}, "colour"),
    ],
)
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
    assert (
        changed.items[0].action == "refused" and "raise the version" in changed.items[0].problems[0]
    )
    newer = run(stage(lib, pdf=PDF + b"more", version="1.1", file="sample-map-v1.1.pdf"))
    assert newer.items[0].action == "new_version" and lib.items.get("sample-map").version == "1.1"
    assert lib.files.exists("items/sample-map/1.0/sample-map-v1.0.pdf")  # the old version is kept
    assert run(stage(lib, version="1.0")).items[0].action == "refused"  # going back is refused
    assert len([e for e in ent.bus.published if e.type.endswith("content.item.published")]) == 2


def test_a_stored_object_with_other_content_is_never_replaced(lib):
    lib.files.objects["items/sample-map/1.0/sample-map-v1.0.pdf"] = (
        b"%PDF-1.4\nleft by a run that failed\n"
    )
    [outcome] = run(stage(lib)).items
    assert outcome.action == "refused" and outcome.problems == [
        "file: other content is already stored for this version"
    ]
    assert lib.items.get("sample-map") is None and lib.files.objects[
        "items/sample-map/1.0/sample-map-v1.0.pdf"
    ].endswith(b"failed\n")


def test_one_batch_never_reads_another(lib):
    stage(lib, prefix="batch-10", sku="sample-guide", file="g.pdf")
    assert [o.sku for o in run(stage(lib)).items] == ["sample-map"]


def test_a_draft_is_stored_but_not_announced_and_the_prefix_is_checked(lib, ent):
    run(stage(lib, status="draft"))
    assert lib.items.get("sample-map").status == "draft" and ent.bus.published == []
    assert (
        run(stage(lib)).items[0].action == "updated" and len(ent.bus.published) == 1
    )  # the draft becomes published
    for bad in ("items/sample-map", "../items", "Batch 1", ""):
        with pytest.raises(ValueError):
            run(bad)
