"""Unit tests for parsing the per-group web-service switch (djehuty.web.ui).

Covers both config formats (JSON and XML), both shapes (a flat default and the
object form with per-group overrides), the api-service back-compat alias, and
value normalisation (whitespace, case, unrecognised values).
"""

import logging

import pytest
from defusedxml import ElementTree

from djehuty.web.config import config
from djehuty.web.config.json_parser import JsonConfigElement
from djehuty.web.ui import read_web_service_configuration

logger = logging.getLogger("test_web_service_config")


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


@pytest.mark.parametrize(
    "root, exp_service, exp_groups",
    [
        # Flat form sets the global default only.
        (_json({"web-service": "legacy"}), "legacy", {}),
        (_xml("<web-service>legacy</web-service>"), "legacy", {}),
        # Object form sets the default and per-group overrides.
        (
            _json(
                {"web-service": {"default": "new", "groups": {"admin": "legacy", "api-v3": "new"}}}
            ),
            "new",
            {"admin": "legacy", "api-v3": "new"},
        ),
        (
            _xml(
                "<web-service><default>new</default>"
                "<groups><admin>legacy</admin></groups></web-service>"
            ),
            "new",
            {"admin": "legacy"},
        ),
        # The old "api-service" key is still accepted.
        (_json({"api-service": "legacy"}), "legacy", {}),
        # An absent (or unrelated) node leaves the defaults untouched.
        (_json({"something-else": "1"}), "new", {}),
        # Whitespace around the value is stripped everywhere it can appear.
        (_xml("<web-service>\n  legacy\n  </web-service>"), "legacy", {}),
        (_xml("<web-service><default>\n legacy \n</default></web-service>"), "legacy", {}),
        (
            _xml("<web-service><groups><admin>\n legacy \n</admin></groups></web-service>"),
            "new",
            {"admin": "legacy"},
        ),
        # The value is matched case-insensitively.
        (_xml("<web-service>LEGACY</web-service>"), "legacy", {}),
    ],
)
def test_read_web_service_configuration(root, exp_service, exp_groups):
    read_web_service_configuration(root, logger)
    assert config.web_service == exp_service
    assert config.web_service_groups == exp_groups


@pytest.mark.parametrize(
    "root, exp_service, exp_groups, bad_value",
    [
        # A typo in the flat/default value keeps the previous default.
        (_xml("<web-service>legcy</web-service>"), "new", {}, "legcy"),
        (_xml("<web-service><default>legcy</default></web-service>"), "new", {}, "legcy"),
        # A typo in a group value drops just that group.
        (
            _xml("<web-service><groups><admin>nope</admin></groups></web-service>"),
            "new",
            {},
            "nope",
        ),
    ],
)
def test_unrecognized_value_is_ignored_and_warns(caplog, root, exp_service, exp_groups, bad_value):
    with caplog.at_level(logging.WARNING):
        read_web_service_configuration(root, logger)
    assert config.web_service == exp_service
    assert config.web_service_groups == exp_groups
    assert bad_value in caplog.text
