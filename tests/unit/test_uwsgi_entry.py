"""Unit tests for the uWSGI entry point (djehuty.web.ui.application).

Covers the dependency and configuration error responses, and that the
dispatcher-wrapped app is built once from the parsed config and reused
across requests.
"""

from types import SimpleNamespace

import pytest

import djehuty.dispatch
from djehuty.web import ui
from djehuty.web.config import config


@pytest.fixture(autouse=True)
def fresh_entry_point(monkeypatch):
    monkeypatch.setattr(ui, "_UWSGI_APP", None)
    monkeypatch.setattr(ui, "UWSGI_DEPENDENCY_LOADED", True)


def _call():
    statuses = []
    body = ui.application({}, lambda status, headers: statuses.append(status))
    return statuses, body


def _install_fake_stack(monkeypatch):
    server = SimpleNamespace(db=object())
    main_calls = []
    build_calls = []

    def fake_main(config_file=None, run_internal_server=True):
        main_calls.append((config_file, run_internal_server))
        return server

    def fake_build(legacy, db, default, overrides):
        build_calls.append((legacy, db, default, overrides))
        return lambda env, start_response: [b"dispatched"]

    monkeypatch.setattr(ui, "main", fake_main)
    monkeypatch.setattr(djehuty.dispatch, "build_wsgi_app", fake_build)
    return server, main_calls, build_calls


def test_missing_uwsgi_dependency_returns_500(monkeypatch):
    monkeypatch.setattr(ui, "UWSGI_DEPENDENCY_LOADED", False)
    statuses, body = _call()
    assert statuses == ["500 Internal Server Error"]
    assert b"uwsgi" in body[0]


def test_missing_config_file_asks_for_the_environment_variable(monkeypatch):
    monkeypatch.delenv("DJEHUTY_CONFIG_FILE", raising=False)
    statuses, body = _call()
    assert statuses == ["200 OK"]
    assert b"DJEHUTY_CONFIG_FILE" in body[0]


def test_first_request_builds_the_dispatcher_from_the_config(monkeypatch):
    monkeypatch.setenv("DJEHUTY_CONFIG_FILE", "/etc/djehuty/config.json")
    monkeypatch.setattr(config, "web_service", "legacy")
    monkeypatch.setattr(config, "web_service_groups", {"admin": "new"})
    server, main_calls, build_calls = _install_fake_stack(monkeypatch)

    _, body = _call()

    assert body == [b"dispatched"]
    assert main_calls == [("/etc/djehuty/config.json", False)]
    assert build_calls == [(server, server.db, "legacy", {"admin": "new"})]


def test_later_requests_reuse_the_cached_app(monkeypatch):
    monkeypatch.setenv("DJEHUTY_CONFIG_FILE", "/etc/djehuty/config.json")
    _, main_calls, build_calls = _install_fake_stack(monkeypatch)

    _, first = _call()
    _, second = _call()

    assert first == [b"dispatched"]
    assert second == [b"dispatched"]
    assert len(main_calls) == 1
    assert len(build_calls) == 1
