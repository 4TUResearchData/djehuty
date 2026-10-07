"""Unit tests for the neutral SQL foundation: engine, app.state wiring, migrate().

No Postgres needed -- SQLite covers the engine/app wiring, and migrate() is
exercised with a stubbed runner to assert the DSN is passed unmasked.
"""

import pytest

from djehuty.api.dependencies import get_sql
from djehuty.application import create_app
from djehuty.services.sql import SqlDatabase
from djehuty.web.config import config


class _DB:
    def account_by_session_token(self, token):
        return None


@pytest.fixture(autouse=True)
def reset_sql_config():
    saved = config.sql_database_url
    yield
    config.sql_database_url = saved


def test_sql_database_builds_engine():
    sql = SqlDatabase("sqlite://")
    try:
        with sql.connect() as conn:
            assert conn is not None
    finally:
        sql.dispose()


def test_app_state_sql_live_when_configured():
    config.sql_database_url = "sqlite://"
    app = create_app(_DB())
    assert isinstance(app.state.sql, SqlDatabase)


def test_app_state_sql_none_when_absent():
    config.sql_database_url = None
    app = create_app(_DB())
    assert app.state.sql is None


def test_get_sql_dependency():
    state = type("State", (), {"sql": "SENTINEL"})()
    request = type("Request", (), {"app": type("App", (), {"state": state})()})()
    assert get_sql(request) == "SENTINEL"

    empty = type("Request", (), {"app": type("App", (), {"state": type("S", (), {})()})()})()
    assert get_sql(empty) is None


def test_migrate_passes_unmasked_dsn(monkeypatch):
    captured = {}

    def fake_upgrade(url, script_location, version_table):
        captured["url"] = url
        captured["script_location"] = script_location
        captured["version_table"] = version_table

    monkeypatch.setattr("djehuty.services.sql.database.upgrade_to_head", fake_upgrade)

    sql = SqlDatabase("postgresql+psycopg://user:secretpw@host:5432/db")
    sql.migrate("/some/migrations", "djehuty_feature_version")

    assert "secretpw" in captured["url"]
    assert "***" not in captured["url"]
    assert captured["script_location"] == "/some/migrations"
    assert captured["version_table"] == "djehuty_feature_version"
