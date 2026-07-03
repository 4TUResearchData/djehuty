"""Unit tests for the WSGI dispatcher (djehuty.dispatch).

Confirms requests route to the new stack or legacy per their group toggle, and
that a missing new stack degrades to legacy instead of failing.
"""

import djehuty.route_groups as rg
from djehuty.route_groups import RouteGroup
from djehuty.dispatch import WebServiceDispatcher, build_wsgi_app


def _legacy(environ, start_response):
    return [b"LEGACY"]


def _new(environ, start_response):
    return [b"NEW"]


def _call(app, path):
    return app({"PATH_INFO": path}, None)


def test_unregistered_path_goes_to_legacy():
    app = WebServiceDispatcher(_legacy, _new, default="new", overrides={})
    assert _call(app, "/v3/x") == [b"LEGACY"]


def test_registered_group_default_new_goes_to_new(monkeypatch):
    monkeypatch.setattr(rg, "ROUTE_GROUPS", (RouteGroup("api-v3", prefixes=("/v3/",)),))
    app = WebServiceDispatcher(_legacy, _new, default="new", overrides={})
    assert _call(app, "/v3/x") == [b"NEW"]


def test_group_pinned_to_legacy(monkeypatch):
    monkeypatch.setattr(rg, "ROUTE_GROUPS", (RouteGroup("api-v3", prefixes=("/v3/",)),))
    app = WebServiceDispatcher(_legacy, _new, default="new", overrides={"api-v3": "legacy"})
    assert _call(app, "/v3/x") == [b"LEGACY"]


def test_build_wsgi_app_returns_dispatcher_that_serves_legacy_by_default():
    # No groups registered: the dispatcher forwards everything to legacy.
    app = build_wsgi_app(_legacy, db=object(), default="new", overrides={})
    assert isinstance(app, WebServiceDispatcher)
    assert _call(app, "/anything") == [b"LEGACY"]
