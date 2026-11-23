import argparse
import importlib
import json
import os
import re
import subprocess  # noqa: S404  # gcloud, with a fixed argument list and no shell
import sys
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import httpx
import yaml
from pydantic import ValidationError

from platform_api.admin.client import AdminClient, AdminError
from platform_api.commerce.public import Promotion
from platform_api.modules import FEATURE_MODULES
from platform_api.settings import Settings
from platform_api.shared.logging import configure_logging

JobTable = dict[str, Callable[[Settings], int]]


class DuplicateJob(Exception):
    pass


def build_registry() -> JobTable:
    registry: JobTable = {}
    owners: dict[str, str] = {}
    sources = [("shared", "platform_api.jobs")] + [
        (name, f"platform_api.{name}.jobs") for name in FEATURE_MODULES
    ]
    for owner, path in sources:
        table: JobTable = importlib.import_module(path).JOBS
        for job_name, job in table.items():
            if job_name in registry:
                raise DuplicateJob(
                    f"job {job_name!r} is registered by both {owners[job_name]!r} and {owner!r}"
                )
            registry[job_name] = job
            owners[job_name] = owner
    return registry


class CliError(Exception):
    """A command that cannot run; the message is plain words for the owner."""


class JobRefusedInLocal(Exception):
    """A commerce job would write to a real Firestore while entitlements stay in memory."""


def _identity_token() -> str:
    try:
        done = subprocess.run(  # noqa: S603
            ["gcloud", "auth", "print-identity-token"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        # gcloud's own output can name the account; it is not repeated.
        raise CliError(
            "Could not get an identity token from gcloud. Run 'gcloud auth login' and try again."
        ) from None
    return done.stdout.strip()


class _Refused(Exception):
    """A command that ran and printed its answer, and whose answer is a refusal: exit 1."""


def admin_client() -> AdminClient:
    """The owner's client: `PLATFORM_API_URL`, and the token of the gcloud account signed in."""
    base_url = os.environ.get("PLATFORM_API_URL", "").strip()
    if not base_url:
        raise CliError("Set PLATFORM_API_URL to the address of platform-api first.")
    return AdminClient(base_url, _identity_token)


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _say(key: str, value: object) -> None:
    """One `key: value` line. Anything shaped like an address is masked."""
    print(_EMAIL.sub("[email]", f"{key}: {value}"))


def _switch(value: str) -> bool:
    if value not in ("true", "false"):
        raise argparse.ArgumentTypeError("use true or false")
    return value == "true"


def _email_from_stdin() -> str:
    email = sys.stdin.readline().strip()
    if not email:
        raise CliError("Type the address on standard input, on one line.")
    return email


def _pairs(values: dict[str, Any]) -> str:
    return " ".join(f"{k}={v}" for k, v in values.items())


def _json_ready(value: object) -> object:
    """YAML reads dates as date objects; the service reads RFC 3339 text."""
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"cannot send a value of type {type(value).__name__}")


def _contact_show(client: AdminClient, args: argparse.Namespace) -> None:
    contact = client.contact_show(_email_from_stdin())
    if contact is None:
        _say("contact", "none")
        return
    _say("contact_id", contact["contact_id"])
    _say("has_member", contact["has_member"])
    for name, channel in contact["channels"].items():
        _say(f"channel.{name}", _pairs(channel))
    for e in contact["entitlements"]:
        keys = ("grant", "source", "label", "status", "valid_until", "campaign")
        _say("entitlement", f"{e['entitlement_id']} " + _pairs({k: e.get(k) for k in keys}))
    for a in contact["audit"]:
        _say("audit", f"{a['at']} {a['actor']} {a['action']} {a['subject']} reason={a['reason']}")


def _grant_create(client: AdminClient, args: argparse.Namespace) -> None:
    email = _email_from_stdin()
    eid = client.grant_create(
        email, args.grant, args.reason, months=args.months, valid_until=args.until
    )
    _say("entitlement_id", eid)


def _grant_revoke(client: AdminClient, args: argparse.Namespace) -> None:
    client.grant_revoke(args.id, args.reason)
    _say("revoked", args.id)


def _load_yaml(path: str) -> object:
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        raise CliError("Could not read that file as YAML.") from None


def _campaign_apply(client: AdminClient, args: argparse.Namespace) -> None:
    loaded = _load_yaml(args.file)
    campaigns = loaded.get("campaigns") if isinstance(loaded, dict) else None
    if not isinstance(campaigns, list):
        raise CliError("The file needs a list under the key 'campaigns'.")
    ready = json.loads(json.dumps(campaigns, default=_json_ready))
    _say("written", client.campaign_apply(ready))


# Written by the service, never from the owner's file.
_PROMOTION_STAMPS = {"counts", "updated_at", "updated_by"}


def _promo_apply(client: AdminClient, args: argparse.Namespace) -> None:
    loaded = _load_yaml(args.file)
    entries = loaded.get("promotions") if isinstance(loaded, dict) else None
    if not isinstance(entries, list):
        raise CliError("The file needs a list under the key 'promotions'.")
    ready = []
    for number, entry in enumerate(entries, start=1):
        if isinstance(entry, dict) and _PROMOTION_STAMPS & set(entry):
            raise CliError(
                f"Promotion {number} in the file: counts and update stamps are written by "
                "the service. Remove them from the file."
            )
        try:
            promotion = Promotion.model_validate(entry)
        except ValidationError as exc:
            # The location and the rule; never the value that was typed.
            problems = "; ".join(
                f"{'.'.join(str(part) for part in e['loc']) or 'entry'}: {e['msg']}"
                for e in exc.errors(include_input=False, include_url=False)
            )
            raise CliError(f"Promotion {number} in the file is not valid: {problems}") from None
        ready.append(promotion.model_dump(mode="json", exclude_unset=True))
    _say("written", client.promotions_put(ready))


MAX_RUNS = 20  # as the route allows


def _run_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"use a whole number from 1 to {MAX_RUNS}") from None
    if not 1 <= limit <= MAX_RUNS:
        raise argparse.ArgumentTypeError(f"use a whole number from 1 to {MAX_RUNS}")
    return limit


_RUN_ACTIONS = ("created", "updated", "ended", "moved", "unchanged", "unseen")


def _runs_show(client: AdminClient, args: argparse.Namespace) -> None:
    for run in client.sync_runs(args.kind, args.limit):
        counts: dict[str, int] = run["counts"]
        actions = {name: counts.get(name, 0) for name in _RUN_ACTIONS}
        others = {k: v for k, v in sorted(counts.items()) if k not in actions and v}
        line = (
            f"{run['kind']} {'dry_run' if run['dry_run'] else 'real'} {run['state']} "
            f"guard={run['guard'] or 'none'} started={run['started_at']} "
            f"finished={run['finished_at'] or 'none'} " + _pairs({**actions, **others})
        )
        _say("run", line)


_LAUNCH_FLAGS = {
    "join_open": "join_open",
    "library_open": "library_open",
    "promotions_open": "promotions_open",
    "terms_version": "required_terms_version",
    "privacy_version": "required_privacy_version",
    "substack_account_url": "substack_account_url",
}


def _launch_set(client: AdminClient, args: argparse.Namespace) -> None:
    switches = {
        field: getattr(args, flag)
        for flag, field in _LAUNCH_FLAGS.items()
        if getattr(args, flag) is not None
    }
    if not switches:
        raise CliError("Name at least one setting to change.")
    for key, value in client.launch_set(switches).items():
        _say(key, value)


def _launch_report(client: AdminClient, args: argparse.Namespace) -> None:
    report = client.launch_report()
    for c in report["campaigns"]:
        _say("campaign", f"{c['slug']} state={c['state']} " + _pairs(c["counts"]))
    _say("members", report["members"])
    for p in client.promotions_list():
        upgrades = (p.get("counts") or {}).get("upgrades_in_window", 0)
        window = f"{p['starts_at']}/{p['ends_at']}"
        _say(
            "promotion",
            f"{p['id']} channel={p['channel']} window={window} upgrades_in_window={upgrades}",
        )


def _support_list(client: AdminClient, args: argparse.Namespace) -> None:
    requests = client.support_list()
    _say("requests", len(requests))
    for r in requests:
        keys = ("member_uid", "kind", "created_at")
        _say("request", f"{r['id']} " + _pairs({k: r[k] for k in keys}) + f" note={r['note']!r}")


def _library_publish(client: AdminClient, args: argparse.Namespace) -> None:
    report = client.library_publish(args.staging_prefix, args.dry_run)
    if report["dry_run"]:
        _say("dry_run", "true")
    _say("items", len(report["items"]))
    if not report["items"]:
        prefix = args.staging_prefix
        print(f"nothing found under {prefix}/; each item needs its own folder {prefix}/<sku>/")
        raise _Refused
    refused = False
    for outcome in report["items"]:
        _say(outcome["sku"], outcome["action"])
        for problem in outcome["problems"]:
            print(_EMAIL.sub("[email]", f"  {problem}"))
        refused = refused or outcome["action"] == "refused"
    if refused:
        raise _Refused


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="platform-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    job_parser = sub.add_parser("job", help="run a job")
    job_parser.add_argument("name")

    contact = sub.add_parser("contact", help="look a contact up").add_subparsers(
        dest="action", required=True
    )
    show = contact.add_parser("show", help="the address is read from standard input")
    show.add_argument("--email-stdin", action="store_true", required=True)
    show.set_defaults(run=_contact_show)

    grant = sub.add_parser("grant", help="grant or revoke by hand").add_subparsers(
        dest="action", required=True
    )
    create = grant.add_parser("create", help="the address is read from standard input")
    create.add_argument("--email-stdin", action="store_true", required=True)
    create.add_argument("--grant", required=True)
    end = create.add_mutually_exclusive_group(required=True)
    end.add_argument("--months", type=int)
    end.add_argument("--until", help="an RFC 3339 time, e.g. 2027-06-01T00:00:00Z")
    create.add_argument("--reason", required=True)
    create.set_defaults(run=_grant_create)
    revoke = grant.add_parser("revoke")
    revoke.add_argument("--id", required=True)
    revoke.add_argument("--reason", required=True)
    revoke.set_defaults(run=_grant_revoke)

    campaign = sub.add_parser("campaign", help="write campaigns").add_subparsers(
        dest="action", required=True
    )
    apply = campaign.add_parser("apply")
    apply.add_argument("--file", required=True)
    apply.set_defaults(run=_campaign_apply)

    promo = sub.add_parser("promo", help="write promotions").add_subparsers(
        dest="action", required=True
    )
    promo_apply = promo.add_parser("apply")
    promo_apply.add_argument("--file", required=True)
    promo_apply.set_defaults(run=_promo_apply)

    runs = sub.add_parser("runs", help="the latest sync runs").add_subparsers(
        dest="action", required=True
    )
    runs_show = runs.add_parser("show")
    runs_show.add_argument("--kind", choices=("stripe_reconcile", "roster_import"))
    runs_show.add_argument("--limit", type=_run_limit, default=MAX_RUNS)
    runs_show.set_defaults(run=_runs_show)

    launch = sub.add_parser("launch", help="the launch switches").add_subparsers(
        dest="action", required=True
    )
    switches = launch.add_parser("set")
    for flag in ("join_open", "library_open", "promotions_open"):
        switches.add_argument("--" + flag.replace("_", "-"), dest=flag, type=_switch)
    for flag in ("terms_version", "privacy_version", "substack_account_url"):
        switches.add_argument("--" + flag.replace("_", "-"), dest=flag)
    switches.set_defaults(run=_launch_set)
    launch.add_parser("report").set_defaults(run=_launch_report)

    support = sub.add_parser("support", help="support requests").add_subparsers(
        dest="action", required=True
    )
    support.add_parser("list").set_defaults(run=_support_list)

    library = sub.add_parser("library", help="the library").add_subparsers(
        dest="action", required=True
    )
    publish = library.add_parser("publish", help="publish the items staged under a prefix")
    publish.add_argument("--staging-prefix", required=True)
    publish.add_argument("--dry-run", action="store_true")
    publish.set_defaults(run=_library_publish)
    return parser


def _run_job(name: str) -> int:
    registry = build_registry()
    job = registry.get(name)
    if job is None:
        known = ", ".join(sorted(registry))
        print(f"unknown job {name!r}; known jobs: {known}", file=sys.stderr)
        return 1  # 2 means only that a guard blocked the run
    from platform_api.commerce import jobs as commerce_jobs

    try:
        settings = Settings()
        configure_logging(settings.service_name)
        if settings.env == "local" and name in commerce_jobs.JOBS:
            # In `local` entitlements are in memory; the job would write to a real Firestore.
            raise JobRefusedInLocal
        _configure_job_runtimes(settings)
    except Exception as exc:
        # As a commerce job that cannot set up: one line naming the class only, since a
        # refused setting's message can repeat the values it was given.
        print(json.dumps({"job": name, "error": type(exc).__name__}))
        return 1
    return job(settings)


def _configure_job_runtimes(settings: Settings) -> None:
    """A job runs on the runtimes the service has (`platform_api.adapters`), with one bus and
    one Firestore client for the process, which the commerce jobs use too."""
    from functools import cache
    from typing import TYPE_CHECKING, cast

    from platform_api.adapters import Lazy, configure_runtimes
    from platform_api.commerce import jobs as commerce_jobs
    from platform_api.shared.bus import EventBus

    if TYPE_CHECKING:
        from google.cloud import firestore

    def pubsub() -> EventBus:
        from google.cloud.pubsub_v1 import PublisherClient  # type: ignore[import-untyped]

        from platform_api.shared.bus import PubSubBus

        return PubSubBus(PublisherClient(), settings.gcp_project, settings.events_topic)

    @cache
    def firestore_client() -> "firestore.Client":
        from google.cloud import firestore

        return firestore.Client(project=settings.gcp_project)

    bus = cast(EventBus, Lazy(pubsub))
    # A job that never uses the contact key (selfcheck) runs without PLATFORM_CONTACT_KEY.
    configure_runtimes(settings, bus, key_required=False, firestore_client=firestore_client)
    commerce_jobs.use_clients(bus, Lazy(firestore_client))


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "job":
        return _run_job(args.name)
    run: Callable[[AdminClient, argparse.Namespace], None] = args.run
    try:
        run(admin_client(), args)
    except AdminError as exc:
        print(_EMAIL.sub("[email]", exc.message), file=sys.stderr)
        return 1
    except CliError as exc:
        print(_EMAIL.sub("[email]", str(exc)), file=sys.stderr)
        return 1
    except _Refused:
        return 1
    except httpx.HTTPError:
        print("Could not reach platform-api at PLATFORM_API_URL.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
