"""Unit tests for parsing the 'sql' relational-store config block (djehuty.web.ui).

Covers both config formats (JSON and XML), the absent/empty cases, and the
${env:}/${file:} indirection (JSON only, resolved by the JSON config parser).
"""

import logging

import pytest
from defusedxml import ElementTree

from djehuty.web.config import config
from djehuty.web.config.json_parser import JsonConfigElement
from djehuty.web.ui import read_sql_configuration

logger = logging.getLogger("test_sql_config")


@pytest.fixture(autouse=True)
def reset_config():
    saved = config.sql_database_url
    config.sql_database_url = None
    yield
    config.sql_database_url = saved


def _json(data):
    return JsonConfigElement("djehuty", data)


def _xml(inner):
    return ElementTree.fromstring(f"<djehuty>{inner}</djehuty>")


def test_json_url():
    read_sql_configuration(_json({"sql": {"url": "postgresql+psycopg://u:p@h/db"}}), logger)
    assert config.sql_database_url == "postgresql+psycopg://u:p@h/db"


def test_xml_url():
    read_sql_configuration(_xml("<sql><url>postgresql+psycopg://u:p@h/db</url></sql>"), logger)
    assert config.sql_database_url == "postgresql+psycopg://u:p@h/db"


def test_absent_block_leaves_none():
    read_sql_configuration(_json({"something-else": "1"}), logger)
    assert config.sql_database_url is None


def test_empty_url_leaves_none():
    read_sql_configuration(_json({"sql": {"url": ""}}), logger)
    assert config.sql_database_url is None


def test_env_reference_is_resolved(monkeypatch):
    monkeypatch.setenv("DJEHUTY_TEST_SQL_URL", "postgresql+psycopg://e:e@h/db")
    read_sql_configuration(_json({"sql": {"url": "${env:DJEHUTY_TEST_SQL_URL}"}}), logger)
    assert config.sql_database_url == "postgresql+psycopg://e:e@h/db"


def test_file_reference_is_resolved(tmp_path):
    secret = tmp_path / "dsn"
    secret.write_text("postgresql+psycopg://f:f@h/db\n")
    read_sql_configuration(_json({"sql": {"url": f"${{file:{secret}}}"}}), logger)
    assert config.sql_database_url == "postgresql+psycopg://f:f@h/db"
