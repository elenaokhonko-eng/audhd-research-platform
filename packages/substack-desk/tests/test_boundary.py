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
        if any(
            name == "platform_api" or name.startswith("platform_api.")
            for name in imported_modules(path)
        )
    ]
    assert offenders == []


def test_the_package_does_not_depend_on_the_platform():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert not any("platform" in dep.lower() for dep in project.get("dependencies", []))
