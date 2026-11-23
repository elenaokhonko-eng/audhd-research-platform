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

from platform_api.admin.client import AdminClient, AdminError
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


def _campaign_apply(client: AdminClient, args: argparse.Namespace) -> None:
    try:
        with open(args.file, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        raise CliError("Could not read that file as YAML.") from None
    campaigns = loaded.get("campaigns") if isinstance(loaded, dict) else None
    if not isinstance(campaigns, list):
        raise CliError("The file needs a list under the key 'campaigns'.")
    ready = json.loads(json.dumps(campaigns, default=_json_ready))
    _say("written", client.campaign_apply(ready))


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


def _support_list(client: AdminClient, args: argparse.Namespace) -> None:
    requests = client.support_list()
    _say("requests", len(requests))
    for r in requests:
        keys = ("member_uid", "kind", "created_at")
        _say("request", f"{r['id']} " + _pairs({k: r[k] for k in keys}) + f" note={r['note']!r}")


def _member_deletions(client: AdminClient, args: argparse.Namespace) -> None:
    for r in client.member_deletions():
        _say("uid", r["uid"])
        _say("requested_at", r["requested_at"])


def _member_delete(client: AdminClient, args: argparse.Namespace) -> None:
    client.member_delete(args.uid)
    _say("deleted", args.uid)


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

    member = sub.add_parser("member", help="deletions members asked for").add_subparsers(
        dest="action", required=True
    )
    member.add_parser("deletions", help="the requests that are waiting").set_defaults(
        run=_member_deletions
    )
    delete = member.add_parser("delete", help="delete a member who asked to be deleted")
    delete.add_argument("--uid", required=True)
    delete.set_defaults(run=_member_delete)
    return parser


def _run_job(name: str) -> int:
    registry = build_registry()
    job = registry.get(name)
    if job is None:
        known = ", ".join(sorted(registry))
        print(f"unknown job {name!r}; known jobs: {known}", file=sys.stderr)
        return 2
    settings = Settings()
    configure_logging(settings.service_name)
    _configure_job_runtimes(settings)
    return job(settings)


def _configure_job_runtimes(settings: Settings) -> None:
    """A job runs on the runtimes the service has (`platform_api.adapters`)."""
    from typing import cast

    from platform_api.adapters import Lazy, configure_runtimes
    from platform_api.shared.bus import EventBus

    def pubsub() -> EventBus:
        from google.cloud.pubsub_v1 import PublisherClient  # type: ignore[import-untyped]

        from platform_api.shared.bus import PubSubBus

        return PubSubBus(PublisherClient(), settings.gcp_project, settings.events_topic)

    # A job that never uses the contact key (selfcheck) runs without PLATFORM_CONTACT_KEY.
    configure_runtimes(settings, cast(EventBus, Lazy(pubsub)), key_required=False)


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
        print(str(exc), file=sys.stderr)
        return 1
    except httpx.HTTPError:
        print("Could not reach platform-api at PLATFORM_API_URL.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
