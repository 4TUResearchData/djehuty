"""Tests for the route-group registry and new/legacy resolution."""

from djehuty.route_groups import RouteGroup, group_for_path, target_for_path


def test_route_group_matches_prefix_and_exact():
    group = RouteGroup("api-v3", prefixes=("/v3/",), exact=("/robots.txt",))
    assert group.matches("/v3/datasets") is True
    assert group.matches("/robots.txt") is True
    assert group.matches("/v2/articles") is False


def test_group_for_path_returns_first_match():
    groups = (
        RouteGroup("api-v2", prefixes=("/v2/",)),
        RouteGroup("api-v3", prefixes=("/v3/",)),
    )
    assert group_for_path("/v3/x", groups).name == "api-v3"
    assert group_for_path("/nope", groups) is None


def test_unregistered_path_resolves_to_legacy():
    # New stack has no router for it.
    assert target_for_path("/v3/x", default="new", overrides={}, groups=()) == "legacy"


def test_registered_group_follows_default():
    groups = (RouteGroup("api-v3", prefixes=("/v3/",)),)
    assert target_for_path("/v3/x", "new", {}, groups) == "new"
    assert target_for_path("/v3/x", "legacy", {}, groups) == "legacy"


def test_override_pins_a_single_group():
    groups = (
        RouteGroup("api-v3", prefixes=("/v3/",)),
        RouteGroup("admin", prefixes=("/admin/",)),
    )
    overrides = {"admin": "legacy"}
    assert target_for_path("/v3/x", "new", overrides, groups) == "new"
    assert target_for_path("/admin/users", "new", overrides, groups) == "legacy"


def test_registry_entries_are_unique_route_groups():
    import djehuty.route_groups as rg

    names = [g.name for g in rg.ROUTE_GROUPS]
    assert all(isinstance(g, RouteGroup) for g in rg.ROUTE_GROUPS)
    assert len(names) == len(set(names))


def test_api_docs_is_served_by_the_new_stack():
    assert group_for_path("/api/docs").name == "api-docs"
    assert target_for_path("/api/docs", "new", {}) == "new"


def test_api_docs_stays_new_even_when_everything_is_disabled():
    # always_new: docs must survive default=legacy and a legacy override.
    assert target_for_path("/api/docs", "legacy", {}) == "new"
    assert target_for_path("/api/docs", "legacy", {"api-docs": "legacy"}) == "new"


def test_always_new_group_ignores_the_toggle():
    groups = (RouteGroup("api-docs", prefixes=("/api/",), always_new=True),)
    assert target_for_path("/api/x", "legacy", {"api-docs": "legacy"}, groups) == "new"
