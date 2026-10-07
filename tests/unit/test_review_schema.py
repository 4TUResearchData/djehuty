"""The field-level review schema migrates to head on SQLite (single revision)."""

import sqlalchemy as sa

from djehuty.api.services.review.setup import _MIGRATIONS_DIR, _VERSION_TABLE
from djehuty.services.sql import upgrade_to_head


def test_initial_migration_creates_review_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'review.db'}"
    upgrade_to_head(url, _MIGRATIONS_DIR, _VERSION_TABLE)

    engine = sa.create_engine(url)
    try:
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"review_round", "review_comment", "review_comment_event"} <= tables
        assert _VERSION_TABLE in tables
        indexes = {i["name"] for i in inspector.get_indexes("review_round")}
        assert "ix_review_round_one_draft" in indexes
    finally:
        engine.dispose()


def test_initial_migration_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'review.db'}"
    upgrade_to_head(url, _MIGRATIONS_DIR, _VERSION_TABLE)
    upgrade_to_head(url, _MIGRATIONS_DIR, _VERSION_TABLE)
