"""Unit test for the generalized Alembic harness (djehuty.services.sql).

Proves that a feature-shaped migrations directory (its own env.py calling the
shared run_migrations, its own version table) upgrades to head against SQLite,
creating both the feature table and the named version table, and that a second
run is a no-op.
"""

import sqlalchemy as sa

from djehuty.services.sql import upgrade_to_head

_ENV_PY = """
from sqlalchemy import Column, Integer, MetaData, String, Table

from djehuty.services.sql import run_migrations

metadata = MetaData()
Table(
    "sql_probe",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("label", String(32)),
)

run_migrations(metadata)
"""

_VERSION_PY = """
import sqlalchemy as sa
from alembic import op

revision = "0001_probe"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sql_probe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=32)),
    )


def downgrade():
    op.drop_table("sql_probe")
"""


def _build_migrations_dir(tmp_path):
    migrations = tmp_path / "migrations"
    (migrations / "versions").mkdir(parents=True)
    (migrations / "env.py").write_text(_ENV_PY)
    (migrations / "script.py.mako").write_text("# unused for upgrade\n")
    (migrations / "versions" / "0001_probe.py").write_text(_VERSION_PY)
    return str(migrations)


def test_upgrade_creates_feature_table_and_version_table(tmp_path):
    url = f"sqlite:///{tmp_path / 'probe.db'}"
    migrations = _build_migrations_dir(tmp_path)

    upgrade_to_head(url, migrations, "djehuty_sql_probe_version")

    engine = sa.create_engine(url)
    try:
        tables = set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert "sql_probe" in tables
    assert "djehuty_sql_probe_version" in tables


def test_upgrade_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'probe.db'}"
    migrations = _build_migrations_dir(tmp_path)

    upgrade_to_head(url, migrations, "djehuty_sql_probe_version")
    # A second upgrade to head must be a no-op, not an error.
    upgrade_to_head(url, migrations, "djehuty_sql_probe_version")
