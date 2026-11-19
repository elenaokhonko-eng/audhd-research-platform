import argparse
import importlib
import sys
from collections.abc import Callable, Sequence

from platform_api.modules import FEATURE_MODULES
from platform_api.settings import Settings

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="platform-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    job_parser = sub.add_parser("job", help="run a job")
    job_parser.add_argument("name")
    args = parser.parse_args(argv)

    registry = build_registry()
    job = registry.get(args.name)
    if job is None:
        known = ", ".join(sorted(registry))
        print(f"unknown job {args.name!r}; known jobs: {known}", file=sys.stderr)
        return 2
    return job(Settings())


if __name__ == "__main__":
    raise SystemExit(main())
