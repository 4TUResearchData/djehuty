"""Programmatic Alembic runner for the shared relational store.

Brings a feature's schema up to head at start-up without the Alembic CLI. The
runner is parameterised by the feature's migrations directory and version table,
so several features can share one database with independent histories. The
Alembic ``Config`` is built in memory (no ``alembic.ini`` on disk); ``env.py``
reads the DSN from the ``-x db_url=...`` option set here.
"""

from alembic import command
from alembic.config import Config


def _alembic_config(database_url: str, script_location: str, version_table: str) -> Config:
    """Build an in-memory Alembic Config for a feature's migrations."""
    cfg = Config()
    cfg.set_main_option("script_location", script_location)
    cfg.set_main_option("version_table", version_table)
    # env.py reads the URL via context.get_x_argument(); feed it as the CLI would.
    cfg.cmd_opts = type("Opts", (), {"x": [f"db_url={database_url}"]})()
    return cfg


def upgrade_to_head(database_url: str, script_location: str, version_table: str) -> None:
    """Upgrade a feature's schema (at SCRIPT_LOCATION) to its latest revision."""
    command.upgrade(_alembic_config(database_url, script_location, version_table), "head")
