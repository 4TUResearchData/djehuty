"""Unit tests for the storage-maintenance seal in the dispatcher."""

import pytest

from djehuty.dispatch import WebServiceDispatcher
from djehuty.web.config import config


def _legacy(environ, start_response):
    return [b"LEGACY"]


def _new(environ, start_response):
    return [b"NEW"]


@pytest.fixture(autouse=True)
def reset_flag():
    saved = (config.storage_maintenance, config.storage_maintenance_retry_after)
    config.storage_maintenance = False
    config.storage_maintenance_retry_after = 3600
    yield
    config.storage_maintenance, config.storage_maintenance_retry_after = saved


def _call(app, path):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = app({"PATH_INFO": path}, start_response)
    return captured, body


def test_sealed_legacy_route_returns_503_with_retry_after():
    config.storage_maintenance = True
    app = WebServiceDispatcher(_legacy, _new, default="new")
    captured, body = _call(app, "/file/abc/def")
    assert captured["status"].startswith("503")
    assert captured["headers"]["Retry-After"] == "3600"
    assert b"StorageMaintenance" in body[0]


def test_sealed_new_stack_route_returns_503():
    config.storage_maintenance = True
    app = WebServiceDispatcher(_legacy, _new, default="new")
    captured, _ = _call(app, "/v3/datasets/123/upload")
    assert captured["status"].startswith("503")


def test_retry_after_is_configurable():
    config.storage_maintenance = True
    config.storage_maintenance_retry_after = 60
    app = WebServiceDispatcher(_legacy, _new, default="new")
    captured, _ = _call(app, "/iiif/v3/uuid/info.json")
    assert captured["headers"]["Retry-After"] == "60"


def test_metadata_route_is_not_sealed():
    config.storage_maintenance = True
    app = WebServiceDispatcher(_legacy, _new, default="new")
    # A metadata GET under /v3 still routes to the new stack.
    assert _call(app, "/v3/datasets/123")[1] == [b"NEW"]


def test_nothing_sealed_when_flag_off():
    app = WebServiceDispatcher(_legacy, _new, default="new")
    # /file is not a registered route group, so it falls through to legacy.
    assert _call(app, "/file/abc/def")[1] == [b"LEGACY"]
