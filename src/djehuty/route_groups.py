"""Which route group owns a path, and whether it resolves to new or legacy.

Pure logic, no framework imports.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteGroup:
    """A named set of paths that migrate and toggle together."""

    name: str
    prefixes: tuple = ()
    exact: tuple = ()
    # Always served by the new stack, ignoring the toggle (e.g. the docs).
    always_new: bool = False

    def matches(self, path: str) -> bool:
        return path in self.exact or any(path.startswith(p) for p in self.prefixes)


# One entry per group; each group's PR appends its own.
ROUTE_GROUPS: tuple = (
    # The umbrella OpenAPI docs (/api/docs, /api/redoc, /api/openapi.json).
    # always_new: the docs stay available even when everything else is legacy.
    RouteGroup("api-docs", prefixes=("/api/",), always_new=True),
    RouteGroup("api-v2", prefixes=("/v2/",)),
)


def group_for_path(path: str, groups=None):
    for group in ROUTE_GROUPS if groups is None else groups:
        if group.matches(path):
            return group
    return None


def target_for_path(path: str, default: str = "new", overrides=None, groups=None) -> str:
    """Return "new" or "legacy" for path. Unregistered paths go to legacy."""
    group = group_for_path(path, groups)
    if group is None:
        return "legacy"
    if group.always_new:
        return "new"
    if overrides and group.name in overrides:
        return overrides[group.name]
    return default
