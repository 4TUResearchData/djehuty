"""Architectural guardrail for the phased migration.

The new HTTP stack must never import the legacy WSGI application. Keeping the
dependency direction one-way is what makes the final removal fearless and each
group independently switchable. The dispatcher composes new and legacy, but it
receives the legacy app as a value; it does not import it.

As each group PR adds packages, extend NEW_STACK_PACKAGES / NEW_STACK_MODULES.
"""

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

LEGACY_WSGI_MODULE = "djehuty.web.wsgi"

# Whole packages that must stay independent of the legacy WSGI app.
NEW_STACK_PACKAGES = ("djehuty.api", "djehuty.services")
# Standalone modules in the new stack.
NEW_STACK_MODULES = ("djehuty.route_groups", "djehuty.application", "djehuty.dispatch")


def _new_stack_files():
    files = []
    for package in NEW_STACK_PACKAGES:
        pkg = importlib.import_module(package)
        for location in pkg.__path__:
            files.extend(Path(location).rglob("*.py"))
    for module in NEW_STACK_MODULES:
        spec = importlib.util.find_spec(module)
        assert spec and spec.origin, f"cannot locate module {module}"
        files.append(Path(spec.origin))
    return sorted(set(files))


def _imported_modules(tree: ast.AST) -> set:
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("path", _new_stack_files(), ids=lambda p: p.name)
def test_new_stack_file_does_not_import_legacy_wsgi(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = _imported_modules(tree)
    offending = {
        m for m in imported if m == LEGACY_WSGI_MODULE or m.startswith(LEGACY_WSGI_MODULE + ".")
    }
    assert not offending, (
        f"{path} imports the legacy WSGI app ({sorted(offending)}). "
        "The new stack must stay independent of djehuty.web.wsgi."
    )
