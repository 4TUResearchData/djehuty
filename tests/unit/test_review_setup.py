"""Boot gating + fail-fast + migrate-once for the field-level review feature."""

import pytest

from djehuty.api.services.review.setup import dataset_review_enabled, setup_dataset_review
from djehuty.web.config import config


class _FakeSql:
    def __init__(self):
        self.calls = []

    def migrate(self, script_location, version_table, retries=1, retry_delay=3.0):
        self.calls.append((script_location, version_table))


def _app(sql):
    return type("App", (), {"state": type("State", (), {"sql": sql})()})()


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    saved = (
        config.enable_dataset_review,
        config.sql_database_url,
        getattr(config, "use_reloader", None),
    )
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    yield
    config.enable_dataset_review, config.sql_database_url, config.use_reloader = saved


def test_disabled_is_noop():
    config.enable_dataset_review = False
    config.sql_database_url = None
    setup_dataset_review(_app(_FakeSql()), "new", {})  # no raise, no migration


def test_enabled_but_review_group_legacy_is_noop():
    config.enable_dataset_review = True
    config.sql_database_url = None
    assert dataset_review_enabled("legacy", {}) is False
    setup_dataset_review(_app(_FakeSql()), "legacy", {})  # gate unmet → no raise


def test_enabled_on_new_without_dsn_fails_fast():
    config.enable_dataset_review = True
    config.sql_database_url = None
    with pytest.raises(RuntimeError):
        setup_dataset_review(_app(_FakeSql()), "new", {})


def test_enabled_with_dsn_runs_the_single_migration():
    config.enable_dataset_review = True
    config.sql_database_url = "postgresql+psycopg://u:p@h/db"
    config.use_reloader = False
    sql = _FakeSql()
    setup_dataset_review(_app(sql), "new", {})
    assert len(sql.calls) == 1
    assert sql.calls[0][1] == "review_alembic_version"


def test_reloader_parent_skips_migration(monkeypatch):
    config.enable_dataset_review = True
    config.sql_database_url = "postgresql+psycopg://u:p@h/db"
    config.use_reloader = True
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)  # the reloader parent
    sql = _FakeSql()
    setup_dataset_review(_app(sql), "new", {})
    assert sql.calls == []
