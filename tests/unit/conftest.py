"""Shared fixtures for unit tests."""

import logging
import os

import pytest
from defusedxml import ElementTree


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXAMPLE_CONFIG_DIR = os.path.join(ROOT_DIR, "etc", "djehuty")


@pytest.fixture
def config_dir():
    """Return the path to the example configuration directory."""
    return EXAMPLE_CONFIG_DIR


@pytest.fixture
def logger():
    """Return a logger instance for tests."""
    return logging.getLogger("test")


# -- Format-specific root fixtures -------------------------------------------


@pytest.fixture
def xml_config_path(config_dir):
    """Return the path to the example XML configuration file."""
    path = os.path.join(config_dir, "djehuty-example-config.xml")
    assert os.path.isfile(path), f"Example config not found: {path}"
    return path


@pytest.fixture
def xml_root(xml_config_path):
    """Parse the example XML config and return the root element."""
    tree = ElementTree.parse(xml_config_path)
    root = tree.getroot()
    assert root.tag == "djehuty"
    return root


# -- Parametrized root fixture -----------------------------------------------
# When JSON support is added, register a json_root fixture above and add
# its name to the params list below.  Every test that uses `config_root`
# will then automatically run against both formats.


@pytest.fixture(params=["xml_root"])
def config_root(request):
    """Yield the parsed config root for each supported format."""
    return request.getfixturevalue(request.param)
