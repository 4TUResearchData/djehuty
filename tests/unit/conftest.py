"""Shared fixtures for unit tests."""

import logging
import os

import pytest
from defusedxml import ElementTree

from djehuty.web.config.json_parser import parse_config_root

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXAMPLE_CONFIG_DIR = os.path.join(ROOT_DIR, "etc", "djehuty")


@pytest.fixture
def config_dir():
    """Return the path to the example configuration directory."""
    return EXAMPLE_CONFIG_DIR


@pytest.fixture
def logger():
    return logging.getLogger("test")


@pytest.fixture
def xml_config_path(config_dir):
    path = os.path.join(config_dir, "djehuty-example-config.xml")
    assert os.path.isfile(path), f"Example config not found: {path}"
    return path


@pytest.fixture
def json_config_path(config_dir):
    path = os.path.join(config_dir, "djehuty-example-config.json")
    assert os.path.isfile(path), f"Example config not found: {path}"
    return path


@pytest.fixture
def xml_root(xml_config_path):
    tree = ElementTree.parse(xml_config_path)
    root = tree.getroot()
    assert root.tag == "djehuty"
    return root


@pytest.fixture
def json_root(json_config_path):
    root = parse_config_root(json_config_path)
    assert root.tag == "djehuty"
    return root


@pytest.fixture(params=["xml_root", "json_root"])
def config_root(request):
    """Yield the parsed config root for each supported format."""
    return request.getfixturevalue(request.param)
