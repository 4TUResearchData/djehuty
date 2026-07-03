"""Architectural guardrail for the phased migration.

The new HTTP stack must never import the legacy WSGI application. Keeping the
dependency direction one-way is what makes the final removal fearless and each
group independently switchable. The dispatcher composes new and legacy, but it
receives the legacy app as a value; it does not import it.

As each group PR adds packages (djehuty.api, djehuty.auth, djehuty.views,
djehuty.services), extend NEW_STACK below.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

LEGACY_WSGI_MODULE = "djehuty.web.wsgi"

# New-stack modules/packages present so far. Grows with each group PR.
NEW_STACK = ("djehuty.route_groups", "djehuty.application", "djehuty.dispatch")


def _module_file(dotted: str) -> Path:
    spec = importlib.util.find_spec(dotted)
    assert spec and spec.origin, f"cannot locate module {dotted}"
    return Path(spec.origin)


def _imported_modules(tree: ast.AST) -> set:
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("dotted", NEW_STACK)
def test_new_stack_module_does_not_import_legacy_wsgi(dotted):
    path = _module_file(dotted)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = _imported_modules(tree)
    offending = {
        m for m in imported if m == LEGACY_WSGI_MODULE or m.startswith(LEGACY_WSGI_MODULE + ".")
    }
    assert not offending, (
        f"{dotted} imports the legacy WSGI app ({sorted(offending)}). "
        "The new stack must stay independent of djehuty.web.wsgi."
    )
