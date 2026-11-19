import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROBE = ROOT / "src/platform_api/library/_probe_forbidden.py"


def lint() -> int:
    return subprocess.run(
        ["lint-imports"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
    ).returncode


def test_skeleton_respects_boundaries() -> None:
    assert lint() == 0


def test_reaching_into_another_module_fails_the_lint() -> None:
    target = ROOT / "src/platform_api/entitlements/_probe_internal.py"  # never a real file
    target.touch()
    PROBE.write_text("from platform_api.entitlements import _probe_internal  # noqa: F401\n")
    try:
        assert lint() != 0
    finally:
        PROBE.unlink()
        target.unlink()


def test_public_interface_is_allowed() -> None:
    PROBE.write_text("from platform_api.entitlements import public  # noqa: F401\n")
    try:
        assert lint() == 0
    finally:
        PROBE.unlink()
