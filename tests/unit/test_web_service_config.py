"""Unit tests for parsing the per-group web-service switch (djehuty.web.ui).

Covers both config formats (JSON and XML), both shapes (a flat default and the
object form with per-group overrides), and the api-service back-compat alias.
"""

import pytest
from defusedxml import ElementTree

from djehuty.web.config import config
from djehuty.web.config.json_parser import JsonConfigElement
from djehuty.web.ui import read_web_service_configuration


@pytest.fixture(autouse=True)
def reset_config():
    saved = (config.web_service, dict(config.web_service_groups))
    config.web_service = "new"
    config.web_service_groups = {}
    yield
    config.web_service, config.web_service_groups = saved[0], saved[1]


def _json(data):
    return JsonConfigElement("djehuty", data)


def _xml(inner):
    return ElementTree.fromstring(f"<djehuty>{inner}</djehuty>")


def test_json_flat_sets_default_only():
    read_web_service_configuration(_json({"web-service": "legacy"}))
    assert config.web_service == "legacy"
    assert config.web_service_groups == {}


def test_json_object_sets_default_and_overrides():
    read_web_service_configuration(
        _json({"web-service": {"default": "new", "groups": {"admin": "legacy", "api-v3": "new"}}})
    )
    assert config.web_service == "new"
    assert config.web_service_groups == {"admin": "legacy", "api-v3": "new"}


def test_xml_flat_sets_default_only():
    read_web_service_configuration(_xml("<web-service>legacy</web-service>"))
    assert config.web_service == "legacy"
    assert config.web_service_groups == {}


def test_xml_object_sets_default_and_overrides():
    read_web_service_configuration(
        _xml(
            "<web-service><default>new</default>"
            "<groups><admin>legacy</admin></groups></web-service>"
        )
    )
    assert config.web_service == "new"
    assert config.web_service_groups == {"admin": "legacy"}


def test_api_service_is_a_backcompat_alias():
    read_web_service_configuration(_json({"api-service": "legacy"}))
    assert config.web_service == "legacy"


def test_absent_config_leaves_defaults():
    read_web_service_configuration(_json({"something-else": "1"}))
    assert config.web_service == "new"
    assert config.web_service_groups == {}
